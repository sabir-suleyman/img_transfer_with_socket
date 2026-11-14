# Soket Programlama ile Resim Gönderme

Bilgisayar Ağları - Temel Protokoller dersi ödevi. İki bilgisayar arasında **TCP soketleri** kullanarak
resim gönderir. İnternet gerekmez; iki bilgisayarın aynı yerel ağda olması yeterlidir
(aynı Wi-Fi, telefon hotspot'u veya Ethernet kablosu).

Linux (Kali) ve Windows 10/11 üzerinde çalışır. Sadece Python standart kütüphanesini kullanır,
ek paket kurmak gerekmez.

## Dosyalar

| Dosya         | Görevi                                                                 |
|---------------|------------------------------------------------------------------------|
| `server.py`   | Resmi **alan** taraf. Gelen resimleri `alinan/` klasörüne kaydeder.      |
| `client.py`   | Resmi **gönderen** taraf.                                              |
| `protocol.py` | İki tarafın ortak kullandığı protokol sabitleri ve `recv_exact` fonksiyonu. |

## Gereksinimler

- Python **3.8 veya üstü** (`python3 --version` / Windows'ta `python --version`)
- İki bilgisayar aynı ağda

## Kullanım

### 1. Aynı ağa bağlanın
Bir bilgisayardan telefonun hotspot'unu açın, iki bilgisayarı da ona bağlayın.

### 2. Sunucu bilgisayarın IP adresini öğrenin
Resmi **alacak** bilgisayarda:

- Linux: `hostname -I` veya `ip -4 addr`
- Windows: `ipconfig` -> Wi-Fi adaptörü altındaki **IPv4 Address** (örn. `192.168.43.25`)

### 3. Sunucuyu başlatın (alıcı bilgisayar)
```bash
python3 server.py        # Windows: python server.py   (veya: py server.py)
```
`[*] Sunucu dinlemede: 0.0.0.0:5001` yazısını görmelisiniz. Durdurmak için `CTRL+C`.

### 4. Resmi gönderin (gönderen bilgisayar)
```bash
python3 client.py <SUNUCU_IP> <RESİM_DOSYASI>
# örnek:
python3 client.py 192.168.43.25 image.jpg
```
Başarılı olursa istemci `Resim aktarımı tamamlandı, sunucu onayladı.` yazar, resim sunucuda
`alinan/` klasöründe görünür. Aynı adlı dosya varsa üzerine yazılmaz (`image_1.jpg`, `image_2.jpg`...).

### Tek bilgisayarda deneme
İki ayrı terminalde:
```bash
python3 server.py
python3 client.py 127.0.0.1 image.jpg
```

## Parametreler

```
server.py [--host ADRES] [-p PORT] [-t SANİYE]
client.py [-p PORT] [-t SANİYE] ip dosya
```

| Parametre        | Varsayılan | Açıklama                                           |
|------------------|-----------:|----------------------------------------------------|
| `-p`, `--port`   | `5001`     | Port numarası (iki tarafta aynı olmalı)            |
| `-t`, `--timeout`| `15`       | Karşı taraftan cevap/veri beklerken zaman aşımı (sn) |
| `--host`         | `0.0.0.0`  | (Sunucu) Dinlenecek adres, varsayılan tüm arayüzler |

Kabul edilen dosya türleri: `.jpg .jpeg .png .gif .bmp .webp` - en fazla 50 MB.

## Protokol

TCP üzerinde, sayılar big-endian (ağ bayt sırası):

```
İstemci -> Sunucu : [2 bayt: ad uzunluğu][ad (UTF-8)][8 bayt: dosya boyutu]   (başlık)
Sunucu  -> İstemci: [1 bayt: durum]    1 = başlık kabul edildi, 2 = reddedildi
İstemci -> Sunucu : [dosya baytları]   (yalnızca başlık kabul edildiyse)
Sunucu  -> İstemci: [1 bayt: durum]    1 = kaydedildi, 3 = başarısız
```

Neden böyle?

- TCP bir **bayt akışıdır**, mesaj sınırı yoktur. Bu yüzden önce dosya boyutu gönderilir ve
  alıcı tam o kadar bayt okur (`recv_exact`).
- Dosya adı ve boyutu, veri gönderilmeden **önce** doğrulanır; geçersiz istekte resim hiç gönderilmez.
- Sunucu istemciye güvenmez: dosya adı temizlenir (`../../x.jpg` -> `x.jpg`), uzantı ve boyut
  sınırı kontrol edilir.
- Bağlantı yarıda koparsa yarım dosya silinir; istemci sonucu sunucunun onayından öğrenir.
- Her adımda zaman aşımı vardır, bu yüzden sessiz kalan bir taraf diğerini sonsuza kadar kilitleyemez.

## Sorun giderme

| Mesaj / durum | Muhtemel neden ve çözüm |
|---|---|
| `Bağlantı reddedildi` | Sunucu çalışmıyor, port yanlış ya da IP yanlış. Sunucunun açık olduğundan ve `-p` değerlerinin aynı olduğundan emin olun. |
| `Zaman aşımı` | Cevap gelmiyor: çoğunlukla **güvenlik duvarı** ya da farklı ağlarda olmak. Aşağıya bakın. |
| `Geçersiz adres` | IP yanlış yazılmış. `192.168.43.25` biçiminde olmalı. |
| `dinlenemiyor (port başka bir programda açık olabilir)` | Port meşgul. Başka bir `-p` deneyin (iki tarafta da). |
| Sunucu `İstek reddedildi` yazıyor | Dosya türü/boyutu/adı geçersiz. Yukarıdaki sınırlara bakın. |

### Bağlanamıyorsanız kontrol listesi

1. **İkisi de aynı ağda mı?** İki bilgisayarın IP'leri aynı bloktan olmalı (örn. ikisi de `192.168.43.x`).
2. **Sunucu bilgisayarın güvenlik duvarı portu engelliyor olabilir.**
   - Windows: sunucuyu ilk çalıştırdığınızda çıkan uyarıda **Özel ağlar**a izin verin. Çıkmadıysa, yönetici
     olarak açılmış bir komut isteminde:
     `netsh advfirewall firewall add rule name="img_transfer" dir=in action=allow protocol=TCP localport=5001`
     Windows hotspot ağını "Genel (Public)" sayıyorsa o profile de izin gerekebilir.
   - Linux: `sudo ufw status` ile bakın; etkinse `sudo ufw allow 5001/tcp`.
3. **Kali sanal makinede mi çalışıyor?** Ağ kartı **NAT** değil, **Köprü (Bridged)** modunda olmalı;
   aksi halde diğer bilgisayar sanal makineye ulaşamaz.
4. **Bazı telefonlar hotspot'a bağlı cihazların birbirini görmesini engeller (istemci yalıtımı).**
   Yukarıdakiler tamamsa hotspot'u diğer cihazda/telefonda deneyin ya da Ethernet kablosuyla doğrudan bağlayın.
5. `ping` ile test ederken dikkat: Windows varsayılan olarak ping'e cevap vermez; ping başarısız olsa da
   TCP çalışabilir. Asıl test sunucuyu açıp istemciyi denemektir.
