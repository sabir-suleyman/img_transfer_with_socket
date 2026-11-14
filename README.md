# Soket Programlama ile Resim Gönderme

Bilgisayar Ağlarında Temel Protokoller dersi ödevi.

| Hazırlayanlar       | Öğrenci No |
|---------------------|-----------:|
| Sabir Süleymanlı    | 502531019  |
| Mert Gökmen         | 502631009  |

İki bilgisayar arasında **TCP soketleri** kullanarak resim gönderir. İnternet gerekmez; iki bilgisayarın
aynı yerel ağda olması yeterlidir (aynı Wi-Fi, telefon hotspot'u veya Ethernet kablosu).

Linux (Kali) ve Windows 10/11 üzerinde çalışır. Sadece Python standart kütüphanesini kullanır,
ek paket kurmak gerekmez.

## Dosyalar

| Dosya         | Görevi                                                                      |
|---------------|-----------------------------------------------------------------------------|
| `transfer.py` | **Ana program.** Tek dosya, iki bilgisayarda da çalışır; **rol (alıcı / gönderici) program çalışırken seçilir.** |
| `server.py`   | Sadece alıcı (sunucu) olarak çalışan ayrı sürüm.                            |
| `client.py`   | Sadece gönderen (istemci) olarak çalışan ayrı sürüm.                        |
| `protocol.py` | `server.py` ve `client.py`'nin ortak kullandığı sabitler ve yardımcılar. `transfer.py` buna ihtiyaç duymaz. |

Dört dosya da **aynı protokolü** konuşur, yani birbirleriyle uyumludur: örneğin bir tarafta `transfer.py`,
diğer tarafta `server.py` / `client.py` kullanılabilir. Alınan resimler `alinan/` klasörüne kaydedilir.

Sadece `transfer.py`'yi diğer bilgisayara kopyalamak yeterlidir.

## Gereksinimler

- Python **3.8 veya üstü** (`python3 --version` / Windows'ta `python --version`)
- İki bilgisayar aynı ağda

## Kullanım

### 1. Aynı ağa bağlanın
Bir bilgisayardan telefonun hotspot'unu açın, iki bilgisayarı da ona bağlayın.

### 2. İki bilgisayarda da programı açın
```bash
python3 transfer.py        # Windows: python transfer.py   (veya: py transfer.py)
```
Menü açılır:

```
=== Resim Transferi ===
  1) Resim AL      (bu bilgisayar alıcı olur ve bekler)
  2) Resim GÖNDER  (bu bilgisayar gönderici olur)
  0) Çıkış
```

### 3. Rolleri seçin
1. **Alacak bilgisayarda `1` yazın.** Ekranda bu bilgisayarın IP adresi görünür (örn. `192.168.43.25`).
   Birden fazla adres çıkarsa gönderenle aynı ağdakini (aynı `192.168.x` bloğu) kullanın.
2. **Gönderecek bilgisayarda `2` yazın.** Alıcının IP adresini ve resmin yolunu girin
   (resim yolu boş bırakılırsa klasördeki `image.jpg` kullanılır).
3. Başarılıysa gönderen `Resim aktarımı tamamlandı, alıcı onayladı.` yazar, resim alıcıda `alinan/` klasöründe görünür.

Alıcı modundan menüye dönmek için `CTRL+C`, programdan çıkmak için menüde `0` yazın.
Roller her seferinde değiştirilebilir; yani aynı iki bilgisayar sırayla hem gönderip hem alabilir.

> IP adresi ekranda görünmezse elle bulun: Linux'ta `hostname -I`, Windows'ta `ipconfig` (Wi-Fi altındaki **IPv4 Address**).

### Menüsüz kullanım (komut satırı)
Menü yerine doğrudan komutla da çalışır; port veya zaman aşımı değiştirmek için bu yolu kullanın:

```bash
python3 transfer.py al                                  # alıcı olarak bekle
python3 transfer.py gonder 192.168.43.25 image.jpg      # gönder
python3 transfer.py al -p 6000 -t 30                    # port 6000, zaman aşımı 30 sn
python3 transfer.py gonder 192.168.43.25 image.jpg -p 6000
```

| Parametre         | Varsayılan | Açıklama                                                    |
|-------------------|-----------:|-------------------------------------------------------------|
| `-p`, `--port`    | `5001`     | Port numarası (iki tarafta aynı olmalı)                     |
| `-t`, `--timeout` | `15`       | Karşı taraftan cevap/veri beklerken zaman aşımı (saniye)    |
| `--host`          | `0.0.0.0`  | (`al`) Dinlenecek adres, varsayılan tüm arayüzler           |

Menü her zaman varsayılan portu (`5001`) kullanır.

Kabul edilen dosya türleri: `.jpg .jpeg .png .gif .bmp .webp` - en fazla 50 MB.

### Ayrı sunucu / istemci dosyalarıyla kullanım
Rolleri iki ayrı dosya olarak çalıştırmak isterseniz (`protocol.py` ile aynı klasörde olmaları gerekir):

```bash
python3 server.py [--host ADRES] [-p PORT] [-t SANİYE]     # alıcı
python3 client.py <ALICI_IP> <RESİM_DOSYASI> [-p PORT] [-t SANİYE]   # gönderen
# örnek:
python3 server.py
python3 client.py 192.168.43.25 image.jpg
```
Bu sürümde `server.py` kendi IP adresini ekrana yazmaz; `hostname -I` (Linux) veya `ipconfig` (Windows) ile bakın.

### Tek bilgisayarda deneme
İki ayrı terminalde:
```bash
python3 transfer.py al                              # 1. terminal
python3 transfer.py gonder 127.0.0.1 image.jpg      # 2. terminal
```

## Protokol

TCP üzerinde, sayılar big-endian (ağ bayt sırası):

```
Gönderen -> Alıcı : [2 bayt: ad uzunluğu][ad (UTF-8)][8 bayt: dosya boyutu]   (başlık)
Alıcı -> Gönderen : [1 bayt: durum]    1 = başlık kabul edildi, 2 = reddedildi
Gönderen -> Alıcı : [dosya baytları]   (yalnızca başlık kabul edildiyse)
Alıcı -> Gönderen : [1 bayt: durum]    1 = kaydedildi, 3 = başarısız
```

Neden böyle?

- TCP bir **bayt akışıdır**, mesaj sınırı yoktur. Bu yüzden önce dosya boyutu gönderilir ve
  alıcı tam o kadar bayt okur (`recv_exact`).
- Dosya adı ve boyutu, veri gönderilmeden **önce** doğrulanır; geçersiz istekte resim hiç gönderilmez.
- Alıcı karşı tarafa güvenmez: dosya adı temizlenir (`../../x.jpg` -> `x.jpg`), uzantı ve boyut
  sınırı kontrol edilir.
- Bağlantı yarıda koparsa yarım dosya silinir; gönderen sonucu alıcının onayından öğrenir.
- Her adımda zaman aşımı vardır, bu yüzden sessiz kalan bir taraf diğerini sonsuza kadar kilitleyemez.

## Sorun giderme

| Mesaj / durum | Muhtemel neden ve çözüm |
|---|---|
| `Bağlantı reddedildi` | Alıcı modu açık değil, port ya da IP yanlış. Karşı tarafta `1) Resim AL` seçili ve çalışıyor olmalı. |
| `Zaman aşımı` | Cevap gelmiyor: çoğunlukla **güvenlik duvarı** ya da farklı ağlarda olmak. Aşağıya bakın. |
| `Geçersiz adres` | IP yanlış yazılmış. `192.168.43.25` biçiminde olmalı. |
| `dinlenemiyor (port başka bir programda açık olabilir)` | Port meşgul (örn. alıcı modu başka bir pencerede açık). Kapatın ya da `al -p 6000` ve `gonder ... -p 6000` ile başka port kullanın. |
| Alıcı `İstek reddedildi` yazıyor | Dosya türü/boyutu/adı geçersiz. Yukarıdaki sınırlara bakın. |

### Bağlanamıyorsanız kontrol listesi

1. **İkisi de aynı ağda mı?** İki bilgisayarın IP'leri aynı bloktan olmalı (örn. ikisi de `192.168.43.x`).
2. **Alıcı bilgisayarın güvenlik duvarı portu engelliyor olabilir.**
   - Windows: alıcı modunu ilk açtığınızda çıkan uyarıda **Özel ağlar**a izin verin. Çıkmadıysa, yönetici
     olarak açılmış bir komut isteminde:
     `netsh advfirewall firewall add rule name="img_transfer" dir=in action=allow protocol=TCP localport=5001`
     Windows hotspot ağını "Genel (Public)" sayıyorsa o profile de izin gerekebilir.
   - Linux: `sudo ufw status` ile bakın; etkinse `sudo ufw allow 5001/tcp`.
3. **Bazı telefonlar hotspot'a bağlı cihazların birbirini görmesini engeller (istemci yalıtımı).**
   Yukarıdakiler tamamsa hotspot'u diğer cihazda/telefonda deneyin ya da Ethernet kablosuyla doğrudan bağlayın.
4. `ping` ile test ederken dikkat: Windows varsayılan olarak ping'e cevap vermez; ping başarısız olsa da
   TCP çalışabilir. Asıl test alıcıyı açıp göndermeyi denemektir.

## Sanal makineyle test (VirtualBox)

İki fiziksel bilgisayar yoksa biri gerçek, biri sanal makine olarak denenebilir:

1. Sanal makinenin **Ağ** ayarında bir ağ kartı **Yalnızca Ana Bilgisayar (Host-only)** olarak ayarlanır.
   Bu ağ internetsiz ve yönlendiricisiz çalışır; ana bilgisayar genelde `192.168.56.1`, sanal makine
   `192.168.56.x` adresini alır. (Alternatif: **Köprü (Bridged)**; bu durumda sanal makine gerçek ağdan IP alır.
   **NAT** modu bu iş için uygun değildir, çünkü dışarıdan sanal makineye bağlanılamaz.)
2. `transfer.py` sanal makineye kopyalanır (örn. ikinci bir NAT kartıyla `git clone`).
3. Bir tarafta `1) AL`, diğerinde `2) GÖNDER` seçilir; ekranda görünen IP girilir. Sonra roller değiştirilip tekrar denenir.
