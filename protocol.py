"""İstemci ve sunucunun ortak kullandığı protokol sabitleri ve yardımcıları.

Protokol (TCP üzerinde, tüm sayılar big-endian / ağ bayt sırası):

    İstemci -> Sunucu : [2 bayt: ad uzunluğu][ad (UTF-8)][8 bayt: dosya boyutu]
    Sunucu  -> İstemci: [1 bayt: durum]   1 = başlık kabul, 2 = reddedildi
    İstemci -> Sunucu : [dosya baytları]  (yalnızca başlık kabul edildiyse)
    Sunucu  -> İstemci: [1 bayt: durum]   1 = kaydedildi, 3 = başarısız
"""

DEFAULT_PORT = 5001
DEFAULT_TIMEOUT = 15                     # Saniye

MAX_FILE_SIZE = 50 * 1024 * 1024         # 50 MB üst sınır
MAX_NAME_BYTES = 255                     # Dosya adı en fazla 255 bayt (UTF-8)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# Sunucunun istemciye gönderdiği 1 baytlık durum kodları
STATUS_OK = 1          # Başlık kabul edildi / resim başarıyla kaydedildi
STATUS_REJECTED = 2    # Başlık geçersiz (ad, uzantı, boyut) - istek reddedildi
STATUS_FAILED = 3      # Aktarım yarım kaldı ya da sunucuda hata oluştu


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
