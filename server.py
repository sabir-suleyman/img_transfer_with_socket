import argparse
import os
import socket
import struct
import sys

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5001
DEFAULT_TIMEOUT = 15                     # İstemci bu kadar saniye sessiz kalırsa vazgeç
BUFFER_SIZE = 4096

SAVE_DIR = "alinan"                      # Gelen resimlerin kaydedileceği klasör
MAX_FILE_SIZE = 50 * 1024 * 1024         # 50 MB üst sınır
MAX_NAME_BYTES = 255                     # Dosya adı en fazla 255 bayt (UTF-8)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# Sunucunun istemciye gönderdiği 1 baytlık durum kodları
STATUS_OK = 1          # Başlık kabul edildi / resim başarıyla kaydedildi
STATUS_REJECTED = 2    # Başlık geçersiz (ad, uzantı, boyut) - istek reddedildi
STATUS_FAILED = 3      # Aktarım yarım kaldı ya da sunucuda hata oluştu

parser = argparse.ArgumentParser(description="Resim alan TCP sunucusu.")
parser.add_argument("--host", default=DEFAULT_HOST,
                    help=f"Dinlenecek adres (varsayılan: {DEFAULT_HOST}, tüm arayüzler)")
parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                    help=f"Dinlenecek port (varsayılan: {DEFAULT_PORT})")
parser.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"İstemciden veri beklerken zaman aşımı, saniye "
                         f"(varsayılan: {DEFAULT_TIMEOUT})")
args = parser.parse_args()

SERVER_HOST = args.host
SERVER_PORT = args.port
CLIENT_TIMEOUT = args.timeout


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


def send_status(sock, status):
    """İstemciye 1 baytlık durum kodu gönderir.

    Bağlantı zaten kopmuşsa göndermek hata verir; bunu sessizce geçiyoruz.
    """
    try:
        sock.sendall(bytes([status]))
    except OSError:
        pass


def sanitize_filename(raw_name):
    """İstemciden gelen dosya adını güvenli hale getirir.

    İstemciye güvenmiyoruz: "../../x.jpg" gibi bir ad dosyayı başka bir
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


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Sunucu hızlıca yeniden başlatıldığında portun meşgul kalmasını engeller.
# Windows'ta SO_REUSEADDR farklı çalışır (aynı portu iki programın açmasına
# izin verir), bu yüzden sadece Linux/macOS'ta ayarlıyoruz.
if os.name != "nt":
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    server_socket.bind((SERVER_HOST, SERVER_PORT))
except OSError as e:
    sys.exit(f"[!] {SERVER_HOST}:{SERVER_PORT} dinlenemiyor "
             f"(port başka bir programda açık olabilir): {e}")
server_socket.listen(5)
# accept() her saniye uyanıp tekrar beklesin. Windows'ta bloklayan accept()
# CTRL+C ile kesilemez; bu kısa zaman aşımı sunucunun kapatılabilmesini sağlar.
server_socket.settimeout(1.0)

print(f"[*] Sunucu dinlemede: {SERVER_HOST}:{SERVER_PORT}")
print("[*] Durdurmak için terminalde CTRL+C yapabilirsiniz.\n")

try:
    while True:
        # İstemci bağlantısını bekle
        try:
            client_socket, client_address = server_socket.accept()
        except socket.timeout:
            continue          # Bağlantı gelmedi, tekrar bekle (CTRL+C'ye fırsat ver)
        print(f"[+] Yeni bağlantı sağlandı: {client_address}")
        partial_file = None   # Yazılmakta olan dosya (hata olursa silinir)

        # Bu istemciyle yapılan her recv() en fazla CLIENT_TIMEOUT saniye bekler.
        # Böylece sessiz kalan bir istemci sunucuyu sonsuza kadar kilitleyemez.
        client_socket.settimeout(CLIENT_TIMEOUT)

        try:
            # Başlık: [2 bayt ad uzunluğu][ad (UTF-8)][8 bayt dosya boyutu]
            name_len = struct.unpack('>H', recv_exact(client_socket, 2))[0]
            if name_len == 0 or name_len > MAX_NAME_BYTES:
                raise ValueError(f"Geçersiz dosya adı uzunluğu: {name_len}")
            raw_name = recv_exact(client_socket, name_len).decode("utf-8")
            file_name = sanitize_filename(raw_name)

            file_size = struct.unpack('>Q', recv_exact(client_socket, 8))[0]
            if file_size == 0 or file_size > MAX_FILE_SIZE:
                raise ValueError(f"Geçersiz dosya boyutu: {file_size} bayt "
                                 f"(izin verilen: 1 - {MAX_FILE_SIZE})")
            print(f"[i] Dosya adı: {file_name} | Boyut: {file_size} bayt")

            # Kayıt klasörünü hazırla; aynı ad varsa üzerine yazma
            os.makedirs(SAVE_DIR, exist_ok=True)
            output_filename = unique_path(SAVE_DIR, file_name)

            # Başlık geçerli: istemciye "veriyi gönderebilirsin" onayı ver
            send_status(client_socket, STATUS_OK)

            # Veriyi alma ve kaydetme
            received_bytes = 0
            first_chunk = True
            header_bytes = b""

            partial_file = output_filename
            with open(output_filename, "wb") as f:
                while received_bytes < file_size:
                    bytes_to_read = min(BUFFER_SIZE, file_size - received_bytes)
                    chunk = client_socket.recv(bytes_to_read)
                    if not chunk:
                        break
                    
                    if first_chunk:
                        header_bytes = chunk[:16]
                        first_chunk = False
                        
                    f.write(chunk)
                    received_bytes += len(chunk)

            # Bağlantı yarıda koptuysa dosya eksiktir: bozuk dosyayı silip uyar
            if received_bytes != file_size:
                os.remove(output_filename)
                partial_file = None
                send_status(client_socket, STATUS_FAILED)
                print(f"[!] Aktarım yarım kaldı ({received_bytes}/{file_size} bayt). "
                      f"Dosya silindi.\n")
                continue

            partial_file = None   # Dosya tam geldi, artık silinmemeli
            send_status(client_socket, STATUS_OK)
            print(f"[+] Kaydedildi: {output_filename}")
            print(f"[+] İlk 16 Bayt (Hex): {header_bytes.hex(' ').upper()}\n")

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
                print(f"[!] Zaman aşımı: istemci {CLIENT_TIMEOUT:g} sn boyunca veri "
                      f"göndermedi. Bağlantı kapatıldı.\n")
            else:
                print(f"[!] Aktarım hatası: {e}\n")
        finally:
            # Sadece bu istemcinin soketini kapat, sunucu açık kalsın
            client_socket.close()

except KeyboardInterrupt:
    print("\n[*] Sunucu kullanıcı tarafından kapatıldı.")
finally:
    server_socket.close()
