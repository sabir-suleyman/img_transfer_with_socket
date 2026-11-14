"""Resim Transferi - sade grafik arayüz (tkinter).

Çalıştırma:
    python3 gui.py          (Windows: python gui.py  veya  py gui.py)

Arayüz yalnızca Python'un standart kütüphanesindeki tkinter'i kullanır;
ek paket kurmak gerekmez. Ağ işlemleri transfer.py'deki aynı kodla yapılır,
bu yüzden komut satırı sürümleriyle (transfer.py / server.py / client.py)
tamamen uyumludur.

Linux'ta tkinter yoksa:  sudo apt install python3-tk
"""

import os
import queue
import socket
import subprocess
import sys
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    sys.exit("[!] tkinter bulunamadı. Linux'ta kurmak için: sudo apt install python3-tk")

# Alınan resimler hangi klasörden başlatılırsa başlatılsın proje klasöründeki
# "alinan/" içine kaydedilsin.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import transfer as tr  # noqa: E402  (chdir'den sonra içe aktarılmalı)

IMAGE_TYPES = [
    ("Resimler", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"),
    ("Tüm dosyalar", "*.*"),
]


class LogWriter:
    """print() çıktısını arayüzün günlük kutusuna yönlendirir (iş parçacığı güvenli)."""

    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("Resim Transferi")
        root.geometry("540x560")
        root.minsize(480, 500)

        self.q = queue.Queue()
        self.log_buffer = ""
        self.stop_event = threading.Event()
        self.receiving = False

        # transfer.py print() ile bilgi veriyor; bunları günlük kutusuna al
        sys.stdout = sys.stderr = LogWriter(self.q)

        notebook = ttk.Notebook(root)
        notebook.pack(fill="x", padx=10, pady=(10, 6))
        self.build_send_tab(notebook)
        self.build_receive_tab(notebook)
        self.build_log()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_queue()

    # ------------------------------------------------------------------
    # GÖNDER sekmesi
    # ------------------------------------------------------------------
    def build_send_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Resim Gönder")
        tab.columnconfigure(1, weight=1)

        self.s_ip = tk.StringVar()
        default_img = os.path.join(BASE_DIR, "image.jpg")
        self.s_path = tk.StringVar(value=default_img if os.path.isfile(default_img) else "")
        self.s_port = tk.StringVar(value=str(tr.DEFAULT_PORT))
        self.s_timeout = tk.StringVar(value=str(tr.DEFAULT_TIMEOUT))

        ttk.Label(tab, text="Alıcının IP adresi:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.s_ip).grid(row=0, column=1, columnspan=2,
                                                    sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(tab, text="Resim:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.s_path).grid(row=1, column=1, sticky="ew",
                                                      pady=4, padx=(8, 4))
        ttk.Button(tab, text="Seç...", command=self.choose_file).grid(row=1, column=2, pady=4)

        opts = ttk.Frame(tab)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(opts, text="Port:").pack(side="left")
        ttk.Entry(opts, textvariable=self.s_port, width=7).pack(side="left", padx=(4, 16))
        ttk.Label(opts, text="Zaman aşımı (sn):").pack(side="left")
        ttk.Entry(opts, textvariable=self.s_timeout, width=6).pack(side="left", padx=4)

        self.s_btn = ttk.Button(tab, text="Gönder", command=self.start_send)
        self.s_btn.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        self.s_bar = ttk.Progressbar(tab, mode="indeterminate")
        self.s_bar.grid(row=4, column=0, columnspan=3, sticky="ew")

    def choose_file(self):
        path = filedialog.askopenfilename(title="Gönderilecek resmi seç", filetypes=IMAGE_TYPES)
        if path:
            self.s_path.set(path)

    def start_send(self):
        ip = self.s_ip.get().strip()
        path = self.s_path.get().strip().strip('"').strip("'")
        if not ip:
            messagebox.showwarning("Eksik bilgi", "Alıcının IP adresini yazın.")
            return
        if not path:
            messagebox.showwarning("Eksik bilgi", "Gönderilecek resmi seçin.")
            return
        values = self.read_numbers(self.s_port, self.s_timeout)
        if values is None:
            return
        port, timeout = values

        self.s_btn.config(state="disabled", text="Gönderiliyor...")
        self.s_bar.start(12)
        threading.Thread(target=self.send_worker, args=(ip, port, path, timeout),
                         daemon=True).start()

    def send_worker(self, ip, port, path, timeout):
        ok = False
        try:
            tr.send_image(ip, port, path, timeout)
            ok = True
        except tr.TransferError as e:
            print(e)
        except Exception as e:  # beklenmeyen hata arayüzü kilitlemesin
            print(f"[!] Beklenmeyen hata: {e}")
        self.q.put(lambda: self.send_done(ok))

    def send_done(self, ok):
        self.s_bar.stop()
        self.s_btn.config(state="normal", text="Gönder")
        if ok:
            messagebox.showinfo("Tamamlandı", "Resim gönderildi, alıcı onayladı.")
        else:
            messagebox.showerror("Gönderilemedi", "Resim gönderilemedi. Ayrıntı için "
                                                  "aşağıdaki günlüğe bakın.")

    # ------------------------------------------------------------------
    # AL sekmesi
    # ------------------------------------------------------------------
    def build_receive_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Resim Al")
        tab.columnconfigure(1, weight=1)

        self.r_port = tk.StringVar(value=str(tr.DEFAULT_PORT))
        self.r_timeout = tk.StringVar(value=str(tr.DEFAULT_TIMEOUT))
        self.r_ips = tk.StringVar(value="(Dinlemeyi başlatınca görünür)")
        self.r_status = tk.StringVar(value="Durum: beklemiyor")

        opts = ttk.Frame(tab)
        opts.grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(opts, text="Port:").pack(side="left")
        self.r_port_entry = ttk.Entry(opts, textvariable=self.r_port, width=7)
        self.r_port_entry.pack(side="left", padx=(4, 16))
        ttk.Label(opts, text="Zaman aşımı (sn):").pack(side="left")
        self.r_timeout_entry = ttk.Entry(opts, textvariable=self.r_timeout, width=6)
        self.r_timeout_entry.pack(side="left", padx=4)

        ttk.Label(tab, text="Bu bilgisayarın IP adresi:").grid(row=1, column=0,
                                                              sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.r_ips, state="readonly").grid(
            row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        ttk.Label(tab, text="Gönderen taraf bu adrese bağlanır (aynı ağdaki adresi kullanın).",
                  foreground="#666666").grid(row=2, column=0, columnspan=2, sticky="w")

        self.r_btn = ttk.Button(tab, text="Dinlemeyi Başlat", command=self.toggle_receive)
        self.r_btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        ttk.Label(tab, textvariable=self.r_status).grid(row=4, column=0, sticky="w")
        ttk.Button(tab, text="Alınan klasörünü aç", command=self.open_folder).grid(
            row=4, column=1, sticky="e")

    def toggle_receive(self):
        if self.receiving:
            self.stop_event.set()
            self.r_btn.config(state="disabled", text="Durduruluyor...")
            return

        values = self.read_numbers(self.r_port, self.r_timeout)
        if values is None:
            return
        port, timeout = values

        self.stop_event = threading.Event()
        self.receiving = True
        self.r_btn.config(text="Dinlemeyi Durdur")
        self.r_port_entry.config(state="disabled")
        self.r_timeout_entry.config(state="disabled")
        self.r_status.set(f"Durum: port {port} dinleniyor...")
        threading.Thread(target=self.receive_worker, args=(port, timeout, self.stop_event),
                         daemon=True).start()

    def receive_worker(self, port, timeout, stop):
        try:
            server_socket = tr.create_server_socket(tr.DEFAULT_HOST, port)
        except tr.TransferError as e:
            print(e)
            self.q.put(self.receive_stopped)
            return

        ips = tr.get_local_ips()
        self.q.put(lambda: self.r_ips.set("   ".join(ips) if ips else
                                          "bulunamadı (ipconfig / hostname -I ile bakın)"))
        print(f"[*] Alma modu: port {port} dinleniyor.")
        try:
            while not stop.is_set():
                try:
                    client_socket, address = server_socket.accept()
                except socket.timeout:
                    continue  # 1 sn'de bir uyanıp durdurma isteğini kontrol eder
                except OSError:
                    break
                print(f"[+] Yeni bağlantı sağlandı: {address}")
                tr.handle_client(client_socket, timeout)
        except Exception as e:
            print(f"[!] Alma modu hatası: {e}")
        finally:
            server_socket.close()
            print("[*] Alma modu durduruldu.\n")
            self.q.put(self.receive_stopped)

    def receive_stopped(self):
        self.receiving = False
        self.r_btn.config(state="normal", text="Dinlemeyi Başlat")
        self.r_port_entry.config(state="normal")
        self.r_timeout_entry.config(state="normal")
        self.r_status.set("Durum: beklemiyor")

    def open_folder(self):
        path = os.path.abspath(tr.SAVE_DIR)
        os.makedirs(path, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)  # noqa: B606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            print(f"[i] Klasör otomatik açılamadı. Konum: {path}")

    # ------------------------------------------------------------------
    # Günlük kutusu
    # ------------------------------------------------------------------
    def build_log(self):
        frame = ttk.LabelFrame(self.root, text="Günlük", padding=6)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.log = tk.Text(frame, height=12, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, command=self.log.yview)
        self.log.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_config("err", foreground="#b00020")
        self.log.tag_config("ok", foreground="#1b7f3b")

        ttk.Button(self.root, text="Günlüğü temizle", command=self.clear_log).pack(
            anchor="e", padx=10, pady=(0, 8))

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def append_log(self, line):
        tag = "err" if line.startswith("[!]") else "ok" if line.startswith("[+]") else None
        self.log.config(state="normal")
        self.log.insert("end", line + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def poll_queue(self):
        """Arka plan iş parçacıklarından gelenleri ana iş parçacığında işler."""
        try:
            while True:
                item = self.q.get_nowait()
                if callable(item):
                    item()
                    continue
                self.log_buffer += item
                while "\n" in self.log_buffer:
                    line, self.log_buffer = self.log_buffer.split("\n", 1)
                    if line.strip():
                        self.append_log(line)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def read_numbers(port_var, timeout_var):
        """Port ve zaman aşımı alanlarını doğrular: (port, timeout) ya da None."""
        try:
            port = int(port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Geçersiz port", "Port 1 ile 65535 arasında bir sayı olmalı.")
            return None
        try:
            timeout = float(timeout_var.get().replace(",", "."))
            if timeout <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Geçersiz zaman aşımı",
                                   "Zaman aşımı 0'dan büyük bir sayı (saniye) olmalı.")
            return None
        return port, timeout

    def on_close(self):
        self.stop_event.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
