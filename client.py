import argparse
import os
import socket
import struct
import sys

from protocol import (
    ALLOWED_EXTENSIONS, DEFAULT_PORT, DEFAULT_TIMEOUT, MAX_FILE_SIZE,
    MAX_NAME_BYTES, STATUS_OK, STATUS_REJECTED,
)

CHUNK_SIZE = 4096


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bir resmi TCP soketiyle sunucuya gönderir.")
    parser.add_argument("ip", help="Sunucunun IP adresi (örn. 192.168.43.10)")
    parser.add_argument("dosya", help="Gönderilecek resmin yolu (örn. image.jpg)")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                        help=f"Sunucu portu (varsayılan: {DEFAULT_PORT})")
    parser.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"Zaman aşımı, saniye (varsayılan: {DEFAULT_TIMEOUT})")
    return parser.parse_args()


def check_file(path):
    """Göndermeden önce dosyayı kontrol eder: (ad, ad_baytları, boyut) döndürür.

    Sunucunun reddedeceği bir şeyi hiç göndermeyelim diye sorun varsa çıkar.
    """
    if not os.path.isfile(path):
        sys.exit(f"[!] Dosya bulunamadı: {path}")

    file_size = os.path.getsize(path)
    file_name = os.path.basename(path)       # Sadece ad (klasör yolu olmadan)
    name_bytes = file_name.encode("utf-8")

    if os.path.splitext(file_name)[1].lower() not in ALLOWED_EXTENSIONS:
        sys.exit(f"[!] Desteklenmeyen dosya türü. İzin verilenler: "
                 f"{', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if file_size == 0:
        sys.exit("[!] Dosya boş.")
    if file_size > MAX_FILE_SIZE:
        sys.exit(f"[!] Dosya çok büyük ({file_size} bayt). "
                 f"En fazla {MAX_FILE_SIZE} bayt gönderilebilir.")
    if len(name_bytes) > MAX_NAME_BYTES:
        sys.exit(f"[!] Dosya adı çok uzun (en fazla {MAX_NAME_BYTES} bayt).")

    return file_name, name_bytes, file_size


def recv_status(sock):
    """Sunucudan 1 baytlık durum kodu okur."""
    data = sock.recv(1)
    if not data:
        raise ConnectionError("Sunucu cevap vermeden bağlantıyı kapattı.")
    return data[0]


def send_image(args, file_name, name_bytes, file_size):
    """Resmi sunucuya gönderir. Sorun olursa hata mesajıyla çıkar."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        # connect/send/recv hiçbiri args.timeout saniyeden uzun beklemesin
        client_socket.settimeout(args.timeout)
        print(f"[*] Bağlanılıyor: {args.ip}:{args.port} | Dosya: {file_name} ({file_size} bayt)")
        client_socket.connect((args.ip, args.port))

        # Başlık: [2 bayt ad uzunluğu][ad (UTF-8)][8 bayt dosya boyutu]
        client_socket.sendall(struct.pack('>H', len(name_bytes)))
        client_socket.sendall(name_bytes)
        client_socket.sendall(struct.pack('>Q', file_size))

        # 1. onay: sunucu başlığı kabul etti mi? Etmediyse veriyi hiç göndermeyiz.
        status = recv_status(client_socket)
        if status == STATUS_REJECTED:
            sys.exit("[!] Sunucu isteği reddetti (dosya adı, uzantı veya boyut kabul edilmedi).")
        if status != STATUS_OK:
            sys.exit(f"[!] Sunucudan beklenmeyen cevap geldi (kod: {status}).")

        # Resim baytlarını aktar
        with open(args.dosya, "rb") as f:
            while (chunk := f.read(CHUNK_SIZE)):
                client_socket.sendall(chunk)

        # 2. onay: sunucu resmi tam alıp kaydetti mi?
        status = recv_status(client_socket)
        if status != STATUS_OK:
            sys.exit("[!] Sunucu resmi kaydedemedi, aktarım başarısız.")


def main():
    args = parse_args()
    file_name, name_bytes, file_size = check_file(args.dosya)

    try:
        send_image(args, file_name, name_bytes, file_size)
        print("[+] Resim aktarımı tamamlandı, sunucu onayladı.")
    except socket.timeout:
        sys.exit(f"[!] Zaman aşımı: {args.timeout:g} saniye içinde cevap alınamadı. "
                 f"IP adresini, portu ve ağ bağlantısını kontrol edin.")
    except ConnectionRefusedError:
        sys.exit(f"[!] Bağlantı reddedildi: {args.ip}:{args.port} adresinde "
                 f"sunucu çalışmıyor ya da port yanlış.")
    except socket.gaierror:
        sys.exit(f"[!] Geçersiz adres: {args.ip}")
    except ConnectionError as e:
        sys.exit(f"[!] Bağlantı koptu: {e}")
    except OSError as e:
        sys.exit(f"[!] Ağ hatası: {e}")


if __name__ == "__main__":
    main()
