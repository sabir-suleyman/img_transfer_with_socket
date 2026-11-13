import os
import socket
import struct
from datetime import datetime

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5001
BUFFER_SIZE = 4096


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


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Sunucu hızlıca yeniden başlatıldığında portun meşgul kalmasını engeller
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(5)

print(f"[*] Sunucu dinlemede: {SERVER_HOST}:{SERVER_PORT}")
print("[*] Durdurmak için terminalde CTRL+C yapabilirsiniz.\n")

try:
    while True:
        # İstemci bağlantısını bekle
        client_socket, client_address = server_socket.accept()
        print(f"[+] Yeni bağlantı sağlandı: {client_address}")

        try:
            # Başlık okuma (8-byte dosya boyutu) - tam 8 bayt gelene kadar bekler
            header = recv_exact(client_socket, 8)

            file_size = struct.unpack('>Q', header)[0]
            print(f"[i] Beklenen Dosya Boyutu: {file_size} bayt")

            # Dinamik dosya adı (tarih_saat)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"gelen_{timestamp}.jpg"

            # Veriyi alma ve kaydetme
            received_bytes = 0
            first_chunk = True
            header_bytes = b""

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
                print(f"[!] Aktarım yarım kaldı ({received_bytes}/{file_size} bayt). "
                      f"Dosya silindi.\n")
                continue

            print(f"[+] Kaydedildi: {output_filename}")
            print(f"[+] İlk 16 Bayt (Hex): {header_bytes.hex(' ').upper()}\n")

        except Exception as e:
            print(f"[!] Aktarım hatası: {e}")
        finally:
            # Sadece bu istemcinin soketini kapat, sunucu açık kalsın
            client_socket.close()

except KeyboardInterrupt:
    print("\n[*] Sunucu kullanıcı tarafından kapatıldı.")
finally:
    server_socket.close()
