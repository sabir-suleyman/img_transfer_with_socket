import socket
import os
import struct

SERVER_IP = '127.0.0.1'
SERVER_PORT = 5001
IMAGE_PATH = 'image.jpg'

file_size = os.path.getsize(IMAGE_PATH)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))

# Önce dosya boyutunu 8 bayt olarak gönder
client_socket.sendall(struct.pack('>Q', file_size))

# Resim baytlarını aktar
with open(IMAGE_PATH, "rb") as f:
    while (chunk := f.read(4096)):
        client_socket.sendall(chunk)

print("[+] Resim aktarımı tamamlandı.")
client_socket.close()