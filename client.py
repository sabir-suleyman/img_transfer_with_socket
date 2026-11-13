import argparse
import os
import socket
import struct
import sys

DEFAULT_PORT = 5001
CHUNK_SIZE = 4096


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bir resmi TCP soketiyle sunucuya gönderir.")
    parser.add_argument("ip", help="Sunucunun IP adresi (örn. 192.168.43.10)")
    parser.add_argument("dosya", help="Gönderilecek resmin yolu (örn. image.jpg)")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                        help=f"Sunucu portu (varsayılan: {DEFAULT_PORT})")
    return parser.parse_args()


args = parse_args()

if not os.path.isfile(args.dosya):
    sys.exit(f"[!] Dosya bulunamadı: {args.dosya}")

file_size = os.path.getsize(args.dosya)

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        print(f"[*] Bağlanılıyor: {args.ip}:{args.port}")
        client_socket.connect((args.ip, args.port))

        # Önce dosya boyutunu 8 bayt olarak gönder
        client_socket.sendall(struct.pack('>Q', file_size))

        # Resim baytlarını aktar
        with open(args.dosya, "rb") as f:
            while (chunk := f.read(CHUNK_SIZE)):
                client_socket.sendall(chunk)

    print("[+] Resim aktarımı tamamlandı.")

except ConnectionRefusedError:
    sys.exit(f"[!] Bağlantı reddedildi: {args.ip}:{args.port} adresinde "
             f"sunucu çalışmıyor ya da port yanlış.")
except socket.gaierror:
    sys.exit(f"[!] Geçersiz adres: {args.ip}")
except OSError as e:
    sys.exit(f"[!] Ağ hatası: {e}")
