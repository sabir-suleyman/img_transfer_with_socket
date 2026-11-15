<p align="right">
  <a href="README.tr.md"><img src="https://img.shields.io/badge/T%C3%BCrk%C3%A7e-oku-red?style=for-the-badge" alt="Türkçe oku"></a>
</p>

# Sending Images with Socket Programming

Assignment for the course *Fundamental Protocols in Computer Networks*.

| Authors             | Student No |
|---------------------|-----------:|
| Sabir Süleymanlı    | 502531019  |
| Mert Gökmen         | 502631009  |

Sends an image from one computer to another using **TCP sockets**. No internet connection is needed;
both computers only have to be on the same local network (same Wi-Fi, phone hotspot, or an Ethernet cable).

Works on Linux (Kali) and Windows 10/11. It uses only the Python standard library
(`tkinter` for the GUI), so there is nothing to install with `pip`.

> **Note:** The program's interface, menu texts, command names (`al`, `gonder`) and messages are in
> Turkish. This README shows them as they appear on screen, with an English translation in parentheses.

## Files

| File          | Purpose                                                                     |
|---------------|-----------------------------------------------------------------------------|
| `gui.py`      | **Graphical interface (tkinter).** Send and receive without typing commands; the easiest way to use the program. |
| `transfer.py` | **Main program (command line).** A single file that runs on both computers; **the role (receiver / sender) is chosen while the program runs.** |
| `server.py`   | A separate version that works only as the receiver (server).                |
| `client.py`   | A separate version that works only as the sender (client).                  |
| `protocol.py` | Constants and helpers shared by `server.py` and `client.py`. `transfer.py` does not need it. |

All five files use **the same network code / protocol** (`gui.py` imports `transfer.py`), so they are compatible
with each other: for example, one side can run `transfer.py` while the other runs `server.py` / `client.py`.
Received images are saved to the `alinan/` ("received") folder.

For the command line, `transfer.py` alone is enough. For the GUI, `gui.py` and `transfer.py` must be in the same
folder (the easiest way is to get the repository with `git clone`).

## Requirements

- Python **3.8 or newer** (`python3 --version` / `python --version` on Windows)
- Both computers on the same network
- For the GUI, `tkinter`: it ships with Python on Windows. On Kali/Debian, if it is missing:
  `sudo apt install python3-tk`

## Using the GUI (recommended)

```bash
git clone https://github.com/sabir-suleyman/img_transfer_with_socket.git
cd img_transfer_with_socket
python3 gui.py             # Windows: python gui.py   (or: py gui.py)
```

A small window opens with two tabs:

- **Resim Al** (Receive Image): Optionally set the port and timeout, then press **Dinlemeyi Başlat**
  (Start Listening). This computer's IP address is shown in the window; give it to the sender. Incoming
  images are saved to the `alinan/` folder (the **Alınan klasörünü aç** / "Open received folder" button opens it).
  When you are done, press **Dinlemeyi Durdur** (Stop Listening).
- **Resim Gönder** (Send Image): Enter the receiver's IP address, choose the image with **Seç...**
  (Browse...) (default: `image.jpg` in the folder) and press **Gönder** (Send). The result is reported in a dialog.

The **Günlük** (Log) box at the bottom of the window shows the same information and error messages that the
command-line version prints (green: success, red: error). Both the sender and the receiver open the same program;
the role is chosen with the tab and can be changed at any time.

If you prefer the command line, the sections below still apply.

## Usage (command line)

### 1. Connect to the same network
Turn on a phone hotspot and connect both computers to it.

### 2. Start the program on both computers
```bash
python3 transfer.py        # Windows: python transfer.py   (or: py transfer.py)
```
A menu appears:

```
=== Resim Transferi ===
  1) Resim AL      (this computer becomes the receiver and waits)
  2) Resim GÖNDER  (this computer becomes the sender)
  0) Çıkış         (exit)
```

### 3. Choose the roles
1. **On the receiving computer, type `1`.** This computer's IP address is shown on screen (e.g. `192.168.43.25`).
   If several addresses are listed, use the one on the same network as the sender (the same `192.168.x` block).
2. **On the sending computer, type `2`.** Enter the receiver's IP address and the path of the image
   (if the path is left empty, `image.jpg` in the folder is used).
3. On success the sender prints `Resim aktarımı tamamlandı, alıcı onayladı.` ("Image transfer completed, receiver confirmed.")
   and the image appears in the receiver's `alinan/` folder.

To go back to the menu from receiver mode press `CTRL+C`; to quit the program type `0` in the menu.
Roles can be changed every time, so the same two computers can take turns sending and receiving.

> If the IP address is not shown on screen, find it manually: `hostname -I` on Linux, `ipconfig` on Windows
> (**IPv4 Address** under Wi-Fi).

### Without the menu (command line)
It also works directly with a command instead of the menu; use this to change the port or the timeout:

```bash
python3 transfer.py al                                  # wait as receiver
python3 transfer.py gonder 192.168.43.25 image.jpg      # send
python3 transfer.py al -p 6000 -t 30                    # port 6000, timeout 30 s
python3 transfer.py gonder 192.168.43.25 image.jpg -p 6000
```

(`al` = receive, `gonder` = send.)

| Parameter         | Default    | Description                                                 |
|-------------------|-----------:|-------------------------------------------------------------|
| `-p`, `--port`    | `5001`     | Port number (must be the same on both sides)                |
| `-t`, `--timeout` | `15`       | Timeout in seconds while waiting for a reply/data from the other side |
| `--host`          | `0.0.0.0`  | (`al`) Address to listen on; all interfaces by default      |

The menu always uses the default port (`5001`).

Accepted file types: `.jpg .jpeg .png .gif .bmp .webp` - at most 50 MB.

### Using the separate server / client files
If you want to run the roles as two separate files (they must be in the same folder as `protocol.py`):

```bash
python3 server.py [--host ADDRESS] [-p PORT] [-t SECONDS]              # receiver
python3 client.py <RECEIVER_IP> <IMAGE_FILE> [-p PORT] [-t SECONDS]     # sender
# example:
python3 server.py
python3 client.py 192.168.43.25 image.jpg
```
In this version `server.py` does not print its own IP address; look it up with `hostname -I` (Linux) or `ipconfig` (Windows).

### Trying it on a single computer
In two separate terminals:
```bash
python3 transfer.py al                              # terminal 1
python3 transfer.py gonder 127.0.0.1 image.jpg      # terminal 2
```

## Protocol

Over TCP, with numbers in big-endian (network byte order):

```
Sender -> Receiver : [2 bytes: name length][name (UTF-8)][8 bytes: file size]   (header)
Receiver -> Sender : [1 byte: status]    1 = header accepted, 2 = rejected
Sender -> Receiver : [file bytes]        (only if the header was accepted)
Receiver -> Sender : [1 byte: status]    1 = saved, 3 = failed
```

Why is it designed this way?

- TCP is a **byte stream** and has no message boundaries. So the file size is sent first and the
  receiver reads exactly that many bytes (`recv_exact`).
- The file name and size are validated **before** any data is sent; on an invalid request the image is never sent.
- The receiver does not trust the other side: the file name is sanitized (`../../x.jpg` -> `x.jpg`), and the
  extension and size limit are checked.
- If the connection drops midway, the partial file is deleted; the sender learns the result from the receiver's confirmation.
- Every step has a timeout, so a silent side cannot block the other one forever.

## Troubleshooting

The program's messages are in Turkish; the table gives the English meaning.

| Message / situation | Likely cause and solution |
|---|---|
| `Bağlantı reddedildi` (connection refused) | Receiver mode is not running, or the port or IP is wrong. `1) Resim AL` must be selected and running on the other side. |
| `Zaman aşımı` (timeout) | No reply: usually the **firewall** or being on different networks. See below. |
| `tkinter bulunamadı` (tkinter not found) | On Kali/Debian install it with `sudo apt install python3-tk`. On Windows, the "tcl/tk" option must be enabled when installing Python. |
| `Geçersiz adres` (invalid address) | The IP was typed wrongly. It must look like `192.168.43.25`. |
| `dinlenemiyor (port başka bir programda açık olabilir)` (cannot listen; the port may be in use) | The port is busy (e.g. receiver mode is open in another window). Close it, or use another port with `al -p 6000` and `gonder ... -p 6000`. |
| Receiver prints `İstek reddedildi` (request rejected) | Invalid file type/size/name. See the limits above. |

### Checklist if you cannot connect

1. **Are both on the same network?** The two computers' IPs must be in the same block (e.g. both `192.168.43.x`).
2. **The receiving computer's firewall may be blocking the port.**
   - Windows: when you first start receiver mode, allow **Private networks** in the prompt that appears. If it did not
     appear, in a command prompt opened as administrator:
     `netsh advfirewall firewall add rule name="img_transfer" dir=in action=allow protocol=TCP localport=5001`
     If Windows treats the hotspot network as "Public", that profile may need permission too.
   - Linux: check with `sudo ufw status`; if it is active, run `sudo ufw allow 5001/tcp`.
3. **Some phones stop devices connected to the hotspot from seeing each other (client isolation).**
   If everything above is fine, try the hotspot on another device/phone, or connect directly with an Ethernet cable.
4. Be careful when testing with `ping`: Windows does not reply to ping by default; TCP may work even if ping fails.
   The real test is starting the receiver and trying to send.

## Testing with a virtual machine (VirtualBox)

If you do not have two physical computers, you can test with one real computer and one virtual machine:

1. In the virtual machine's **Network** settings, set one network adapter to **Host-only**.
   This network works without internet and without a router; the host usually gets `192.168.56.1` and the virtual
   machine gets `192.168.56.x`. (Alternative: **Bridged**; the virtual machine then gets an IP from the real network.
   **NAT** mode is not suitable for this, because the virtual machine cannot be reached from outside.)
2. Copy `transfer.py` to the virtual machine (e.g. `git clone` over a second NAT adapter).
3. Choose `1) AL` (receive) on one side and `2) GÖNDER` (send) on the other, and enter the IP shown on screen. Then swap the roles and try again.
