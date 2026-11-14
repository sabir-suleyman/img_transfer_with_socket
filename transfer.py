"""Resim Transferi: TCP soketleriyle iki bilgisayar arasında resim gönderme/alma.

Tek dosya, iki rol. Hangi tarafın alıcı (sunucu), hangisinin gönderici (istemci)
olacağı program çalışırken seçilir.

Kullanım:
    python3 transfer.py                        Menü açılır (1: Al, 2: Gönder)
    python3 transfer.py al [-p PORT]           Doğrudan alma moduna geç
    python3 transfer.py gonder IP DOSYA        Doğrudan gönderme moduna geç

Protokol (TCP üzerinde, tüm sayılar big-endian / ağ bayt sırası):

    Gönderen -> Alan  : [2 bayt: ad uzunluğu][ad (UTF-8)][8 bayt: dosya boyutu]
    Alan -> Gönderen  : [1 bayt: durum]   1 = başlık kabul, 2 = reddedildi
    Gönderen -> Alan  : [dosya baytları]  (yalnızca başlık kabul edildiyse)
    Alan -> Gönderen  : [1 bayt: durum]   1 = kaydedildi, 3 = başarısız
"""

import argparse
import os
import re
import socket
import struct
import subprocess
import sys

# ============================================================================
# Protokol sabitleri
# ============================================================================

DEFAULT_HOST = '0.0.0.0'                 # Tüm ağ arayüzlerini dinle
DEFAULT_PORT = 5001
DEFAULT_TIMEOUT = 15                     # Saniye
BUFFER_SIZE = 4096
SAVE_DIR = "alinan"                      # Gelen resimlerin kaydedileceği klasör
ACCEPT_POLL_SECONDS = 1.0                # accept() bu aralıkla uyanır (CTRL+C için)

MAX_FILE_SIZE = 50 * 1024 * 1024         # 50 MB üst sınır
MAX_NAME_BYTES = 255                     # Dosya adı en fazla 255 bayt (UTF-8)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# Alıcının göndericiye yolladığı 1 baytlık durum kodları
STATUS_OK = 1          # Başlık kabul edildi / resim başarıyla kaydedildi
STATUS_REJECTED = 2    # Başlık geçersiz (ad, uzantı, boyut) - istek reddedildi
STATUS_FAILED = 3      # Aktarım yarım kaldı ya da alıcıda hata oluştu


class TransferError(Exception):
    """Kullanıcıya olduğu gibi gösterilecek, anlaşılır bir hata mesajı taşır."""


def recv_exact(sock, n):
    """Soketten TAM olarak n bayt okur.

    TCP bir bayt akışıdır: recv(8) çağrısı 8 bayt yerine 3 bayt döndürebilir.
    Bu yüzden istenen miktar tamamlanana kadar döngüyle okuruz.
    Karşı taraf bağlantıyı erken kapatırsa ConnectionError fırlatır.
    """
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Bağlantı, beklenen veri gelmeden kapandı.")
        data += chunk
    return data


# ============================================================================
# ALMA tarafı (sunucu)
# ============================================================================

def send_status(sock, status):
    """Göndericiye 1 baytlık durum kodu yollar.

    Bağlantı zaten kopmuşsa göndermek hata verir; bunu sessizce geçiyoruz.
    """
    try:
        sock.sendall(bytes([status]))
    except OSError:
        pass


def sanitize_filename(raw_name):
    """Karşıdan gelen dosya adını güvenli hale getirir.

    Karşı tarafa güvenmiyoruz: "../../x.jpg" gibi bir ad dosyayı başka bir
    klasöre yazdırabilir. Geçersizse ValueError fırlatır.
    """
    # Windows tarzı yolları (C:\\a\\b.jpg) Linux'ta da ayırabilmek için
    name = raw_name.replace("\\", "/")
    name = os.path.basename(name)            # "../../x.jpg" -> "x.jpg"
    # Windows'ta yasak karakterleri ve kontrol karakterlerini "_" yap
    name = "".join("_" if (c in '<>:"|?*' or ord(c) < 32) else c for c in name)
    name = name.strip(" .")
    if not name:
        raise ValueError("Geçersiz dosya adı.")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"İzin verilmeyen dosya uzantısı: {ext or '(yok)'}")
    return name


def unique_path(folder, name):
    """Aynı adlı dosya varsa üzerine yazmamak için ad_1.jpg, ad_2.jpg ... üretir."""
    base, ext = os.path.splitext(name)
    path = os.path.join(folder, name)
    counter = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{counter}{ext}")
        counter += 1
    return path


def get_local_ips():
    """Bu bilgisayarın yerel ağdaki IPv4 adreslerini bulmaya çalışır (en iyi çaba).

    Karşı tarafın hangi IP'ye bağlanacağını bilmesi gerekir. Bulunamazsa boş
    liste döner; kullanıcı ipconfig / hostname -I ile kendisi bakabilir.
    """
    ips = []

    def add(ip):
        if ip and not ip.startswith(("127.", "169.254.", "0.")) and ip not in ips:
            ips.append(ip)

    # 1) Hangi arayüzün kullanılacağını işletim sistemine sor (paket gönderilmez)
    for target in ("8.8.8.8", "10.0.0.1", "172.16.0.1", "192.168.0.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 9))
                add(s.getsockname()[0])
        except OSError:
            pass

    # 2) Tüm arayüzlerin adreslerini sistem komutundan oku (internetsiz ağlarda da çalışır)
    try:
        if os.name == "nt":
            out = subprocess.run(["ipconfig"], capture_output=True, timeout=5).stdout
            for line in out.decode("utf-8", "ignore").splitlines():
                if "IPv4" in line:
                    for ip in re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", line):
                        add(ip)
        else:
            out = subprocess.run(["hostname", "-I"], capture_output=True, timeout=5).stdout
            for ip in re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", out.decode("utf-8", "ignore")):
                add(ip)
    except (OSError, subprocess.SubprocessError):
        pass

    return ips


def create_server_socket(host, port):
    """Dinleyen sunucu soketini oluşturur. Port kullanılamıyorsa TransferError fırlatır."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Hızlı yeniden başlatmada portun meşgul kalmasını engeller.
    # Windows'ta SO_REUSEADDR farklı çalışır (aynı portu iki programın açmasına
    # izin verir), bu yüzden sadece Linux/macOS'ta ayarlıyoruz.
    if os.name != "nt":
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
    except OSError as e:
        server_socket.close()
        raise TransferError(f"[!] {host}:{port} dinlenemiyor "
                            f"(port başka bir programda açık olabilir): {e}")
    server_socket.listen(5)

    # accept() her saniye uyanıp tekrar beklesin. Windows'ta bloklayan accept()
    # CTRL+C ile kesilemez; bu kısa zaman aşımı kapatılabilmeyi sağlar.
    server_socket.settimeout(ACCEPT_POLL_SECONDS)
    return server_socket


def receive_header(client_socket):
    """Başlığı okur ve doğrular: (dosya_adı, dosya_boyutu) döndürür.

    Geçersiz başlıkta ValueError fırlatır.
    Başlık: [2 bayt ad uzunluğu][ad (UTF-8)][8 bayt dosya boyutu]
    """
    name_len = struct.unpack('>H', recv_exact(client_socket, 2))[0]
    if name_len == 0 or name_len > MAX_NAME_BYTES:
        raise ValueError(f"Geçersiz dosya adı uzunluğu: {name_len}")
    raw_name = recv_exact(client_socket, name_len).decode("utf-8")
    file_name = sanitize_filename(raw_name)

    file_size = struct.unpack('>Q', recv_exact(client_socket, 8))[0]
    if file_size == 0 or file_size > MAX_FILE_SIZE:
        raise ValueError(f"Geçersiz dosya boyutu: {file_size} bayt "
                         f"(izin verilen: 1 - {MAX_FILE_SIZE})")
    return file_name, file_size


def receive_file(client_socket, output_path, file_size):
    """Dosya baytlarını alıp output_path'e yazar.

    (alınan_bayt_sayısı, ilk_16_bayt) döndürür. Bağlantı yarıda koparsa
    alınan sayı file_size'tan küçük olur; kontrolü çağıran yapar.
    """
    received_bytes = 0
    first_bytes = b""

    with open(output_path, "wb") as f:
        while received_bytes < file_size:
            bytes_to_read = min(BUFFER_SIZE, file_size - received_bytes)
            chunk = client_socket.recv(bytes_to_read)
            if not chunk:
                break

            if not first_bytes:
                first_bytes = chunk[:16]

            f.write(chunk)
            received_bytes += len(chunk)

    return received_bytes, first_bytes


def handle_client(client_socket, timeout):
    """Tek bir göndericiyi baştan sona işler ve soketini kapatır."""
    partial_file = None   # Yazılmakta olan dosya (hata olursa silinir)

    # Bu bağlantıdaki her recv() en fazla `timeout` saniye bekler.
    # Böylece sessiz kalan bir taraf bizi sonsuza kadar kilitleyemez.
    client_socket.settimeout(timeout)

    try:
        file_name, file_size = receive_header(client_socket)
        print(f"[i] Dosya adı: {file_name} | Boyut: {file_size} bayt")

        # Kayıt klasörünü hazırla; aynı ad varsa üzerine yazma
        os.makedirs(SAVE_DIR, exist_ok=True)
        output_path = unique_path(SAVE_DIR, file_name)

        # Başlık geçerli: göndericiye "veriyi gönderebilirsin" onayı ver
        send_status(client_socket, STATUS_OK)

        partial_file = output_path
        received_bytes, first_bytes = receive_file(client_socket, output_path, file_size)

        # Bağlantı yarıda koptuysa dosya eksiktir: bozuk dosyayı silip uyar
        if received_bytes != file_size:
            os.remove(output_path)
            partial_file = None
            send_status(client_socket, STATUS_FAILED)
            print(f"[!] Aktarım yarım kaldı ({received_bytes}/{file_size} bayt). "
                  f"Dosya silindi.\n")
            return

        partial_file = None   # Dosya tam geldi, artık silinmemeli
        send_status(client_socket, STATUS_OK)
        print(f"[+] Kaydedildi: {output_path}")
        print(f"[+] İlk 16 Bayt (Hex): {first_bytes.hex(' ').upper()}\n")

    except ValueError as e:
        # Geçersiz başlık (ad, uzantı, boyut vb.) -> istek reddedilir
        send_status(client_socket, STATUS_REJECTED)
        print(f"[!] İstek reddedildi: {e}\n")
    except Exception as e:
        # Beklenmeyen hata (bağlantı kopması, disk hatası...): yarım dosyayı sil
        if partial_file and os.path.exists(partial_file):
            os.remove(partial_file)
        send_status(client_socket, STATUS_FAILED)
        if isinstance(e, socket.timeout):
            print(f"[!] Zaman aşımı: karşı taraf {timeout:g} sn boyunca veri "
                  f"göndermedi. Bağlantı kapatıldı.\n")
        else:
            print(f"[!] Aktarım hatası: {e}\n")
    finally:
        # Sadece bu bağlantıyı kapat, dinlemeye devam et
        client_socket.close()


def run_receiver(host, port, timeout):
    """Alma modu: CTRL+C'ye kadar gelen resimleri kabul eder."""
    server_socket = create_server_socket(host, port)

    print(f"[*] Alma modu: {host}:{port} dinleniyor")
    if host == DEFAULT_HOST:
        ips = get_local_ips()
        if ips:
            print("[*] Gönderen taraf bu bilgisayara şu IP adres(ler)inden bağlanabilir:")
            for ip in ips:
                print(f"      {ip}")
            print("    (Hangisi doğru? Gönderenle aynı ağdaki adres; örn. ikisi de 192.168.x.x)")
        else:
            print("[*] IP adresinizi bulamadım: Windows'ta 'ipconfig', Linux'ta "
                  "'hostname -I' yazıp bakın.")
    print("[*] Durdurmak için CTRL+C.\n")

    try:
        while True:
            try:
                client_socket, client_address = server_socket.accept()
            except socket.timeout:
                continue      # Bağlantı gelmedi, tekrar bekle (CTRL+C'ye fırsat ver)
            print(f"[+] Yeni bağlantı sağlandı: {client_address}")
            handle_client(client_socket, timeout)
    except KeyboardInterrupt:
        print("\n[*] Alma modu kapatıldı.")
    finally:
        server_socket.close()


# ============================================================================
# GÖNDERME tarafı (istemci)
# ============================================================================

def check_file(path):
    """Göndermeden önce dosyayı kontrol eder: (ad, ad_baytları, boyut) döndürür.

    Alıcının reddedeceği bir şeyi hiç göndermeyelim diye sorun varsa TransferError fırlatır.
    """
    if not os.path.isfile(path):
        raise TransferError(f"[!] Dosya bulunamadı: {path}")

    file_size = os.path.getsize(path)
    file_name = os.path.basename(path)       # Sadece ad (klasör yolu olmadan)
    name_bytes = file_name.encode("utf-8")

    if os.path.splitext(file_name)[1].lower() not in ALLOWED_EXTENSIONS:
        raise TransferError(f"[!] Desteklenmeyen dosya türü. İzin verilenler: "
                            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if file_size == 0:
        raise TransferError("[!] Dosya boş.")
    if file_size > MAX_FILE_SIZE:
        raise TransferError(f"[!] Dosya çok büyük ({file_size} bayt). "
                            f"En fazla {MAX_FILE_SIZE} bayt gönderilebilir.")
    if len(name_bytes) > MAX_NAME_BYTES:
        raise TransferError(f"[!] Dosya adı çok uzun (en fazla {MAX_NAME_BYTES} bayt).")

    return file_name, name_bytes, file_size


def recv_status(sock):
    """Alıcıdan 1 baytlık durum kodu okur."""
    data = sock.recv(1)
    if not data:
        raise ConnectionError("Karşı taraf cevap vermeden bağlantıyı kapattı.")
    return data[0]


def _transfer(ip, port, path, timeout, file_name, name_bytes, file_size):
    """Ağ işlemlerinin kendisi. Soket hataları çağıran tarafından çevrilir."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # connect/send/recv hiçbiri `timeout` saniyeden uzun beklemesin
        sock.settimeout(timeout)
        print(f"[*] Bağlanılıyor: {ip}:{port} | Dosya: {file_name} ({file_size} bayt)")
        sock.connect((ip, port))

        # Başlık: [2 bayt ad uzunluğu][ad (UTF-8)][8 bayt dosya boyutu]
        sock.sendall(struct.pack('>H', len(name_bytes)))
        sock.sendall(name_bytes)
        sock.sendall(struct.pack('>Q', file_size))

        # 1. onay: alıcı başlığı kabul etti mi? Etmediyse veriyi hiç göndermeyiz.
        status = recv_status(sock)
        if status == STATUS_REJECTED:
            raise TransferError("[!] Alıcı isteği reddetti "
                                "(dosya adı, uzantı veya boyut kabul edilmedi).")
        if status != STATUS_OK:
            raise TransferError(f"[!] Alıcıdan beklenmeyen cevap geldi (kod: {status}).")

        # Resim baytlarını aktar
        with open(path, "rb") as f:
            while (chunk := f.read(BUFFER_SIZE)):
                sock.sendall(chunk)

        # 2. onay: alıcı resmi tam alıp kaydetti mi?
        status = recv_status(sock)
        if status != STATUS_OK:
            raise TransferError("[!] Alıcı resmi kaydedemedi, aktarım başarısız.")


def send_image(ip, port, path, timeout):
    """Resmi gönderir. Her türlü sorunda anlaşılır bir TransferError fırlatır."""
    file_name, name_bytes, file_size = check_file(path)
    try:
        _transfer(ip, port, path, timeout, file_name, name_bytes, file_size)
    except socket.timeout:
        raise TransferError(f"[!] Zaman aşımı: {timeout:g} saniye içinde cevap alınamadı. "
                            f"IP adresini, portu, güvenlik duvarını ve ağ bağlantısını kontrol edin.")
    except ConnectionRefusedError:
        raise TransferError(f"[!] Bağlantı reddedildi: {ip}:{port} adresinde alıcı "
                            f"çalışmıyor ya da port yanlış.")
    except socket.gaierror:
        raise TransferError(f"[!] Geçersiz adres: {ip}")
    except ConnectionError as e:
        raise TransferError(f"[!] Bağlantı koptu: {e}")
    except OSError as e:
        raise TransferError(f"[!] Ağ hatası: {e}")
    print("[+] Resim aktarımı tamamlandı, alıcı onayladı.")


# ============================================================================
# Menü ve komut satırı
# ============================================================================

def ask(prompt, default=None):
    """Kullanıcıdan metin ister. Boş bırakılırsa varsayılan değeri döndürür."""
    text = f"{prompt} [{default}]: " if default else f"{prompt}: "
    # Windows'ta dosya sürüklenince/yapıştırılınca yol tırnak içinde gelebilir
    value = input(text).strip().strip('"').strip("'")
    return value or default or ""


def menu_receive():
    run_receiver(DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT)


def menu_send():
    ip = ask("Alıcı bilgisayarın IP adresi (alıcı ekranında yazıyor)")
    if not ip:
        raise TransferError("[!] IP adresi girilmedi.")
    default_file = "image.jpg" if os.path.isfile("image.jpg") else None
    path = ask("Gönderilecek resmin yolu", default_file)
    if not path:
        raise TransferError("[!] Dosya yolu girilmedi.")
    send_image(ip, DEFAULT_PORT, path, DEFAULT_TIMEOUT)


def interactive_menu():
    """Rolü çalışırken seçtiren menü. CTRL+C ya da 0 ile çıkılır."""
    actions = {"1": menu_receive, "2": menu_send}
    while True:
        print("\n=== Resim Transferi ===")
        print("  1) Resim AL      (bu bilgisayar alıcı olur ve bekler)")
        print("  2) Resim GÖNDER  (bu bilgisayar gönderici olur)")
        print("  0) Çıkış")
        try:
            choice = input("Seçiminiz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        action = actions.get(choice)
        if action is None:
            print("[!] Geçersiz seçim. 1, 2 veya 0 yazın.")
            continue
        try:
            action()
        except TransferError as e:
            print(e)
        except (EOFError, KeyboardInterrupt):
            print("\n[*] İptal edildi.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="TCP soketleriyle resim gönder/al. Argümansız çalıştırırsanız menü açılır.")
    sub = parser.add_subparsers(dest="komut", metavar="{al,gonder}")

    def add_common(p):
        p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                       help=f"Port numarası (varsayılan: {DEFAULT_PORT}; iki tarafta aynı olmalı)")
        p.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT,
                       help=f"Zaman aşımı, saniye (varsayılan: {DEFAULT_TIMEOUT})")

    p_al = sub.add_parser("al", help="Resim al (alıcı olarak bekle)")
    p_al.add_argument("--host", default=DEFAULT_HOST,
                      help=f"Dinlenecek adres (varsayılan: {DEFAULT_HOST}, tüm arayüzler)")
    add_common(p_al)

    p_gonder = sub.add_parser("gonder", help="Resim gönder")
    p_gonder.add_argument("ip", help="Alıcının IP adresi (örn. 192.168.43.10)")
    p_gonder.add_argument("dosya", help="Gönderilecek resmin yolu (örn. image.jpg)")
    add_common(p_gonder)

    return parser.parse_args()


def main():
    args = parse_args()
    try:
        if args.komut == "al":
            run_receiver(args.host, args.port, args.timeout)
        elif args.komut == "gonder":
            send_image(args.ip, args.port, args.dosya, args.timeout)
        else:
            interactive_menu()
    except TransferError as e:
        sys.exit(str(e))
    except KeyboardInterrupt:
        sys.exit("\n[*] İptal edildi.")


if __name__ == "__main__":
    main()
