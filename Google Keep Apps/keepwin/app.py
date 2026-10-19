"""KeepWin - Google Keep icin Windows masaustu istemcisi (gkeepapi tabanli, resmi olmayan)."""
import json, os, secrets, threading, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import gkeepapi
import gpsoauth
import keyring

SERVICE = "KeepWin"
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KeepWin")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
os.makedirs(DATA_DIR, exist_ok=True)

COLORS = {
    "Beyaz": gkeepapi.node.ColorValue.White, "Kirmizi": gkeepapi.node.ColorValue.Red,
    "Turuncu": gkeepapi.node.ColorValue.Orange, "Sari": gkeepapi.node.ColorValue.Yellow,
    "Yesil": gkeepapi.node.ColorValue.Green, "Turkuaz": gkeepapi.node.ColorValue.Teal,
    "Mavi": gkeepapi.node.ColorValue.Blue, "Mor": gkeepapi.node.ColorValue.Purple,
    "Pembe": gkeepapi.node.ColorValue.Pink, "Gri": gkeepapi.node.ColorValue.Gray,
}
HEX = {"WHITE": "#ffffff", "RED": "#f28b82", "ORANGE": "#fbbc04", "YELLOW": "#fff475",
       "GREEN": "#ccff90", "TEAL": "#a7ffeb", "BLUE": "#aecbfa", "PURPLE": "#d7aefb",
       "PINK": "#fdcfe8", "GRAY": "#e8eaed", "BROWN": "#e6c9a8", "CERULEAN": "#cbf0f8"}
UNCHECKED, CHECKED = "\u2610 ", "\u2611 "


def load_creds():
    email = keyring.get_password(SERVICE, "email")
    token = keyring.get_password(SERVICE, "master_token") if email else None
    return email, token


def save_creds(email, token):
    keyring.set_password(SERVICE, "email", email)
    keyring.set_password(SERVICE, "master_token", token)


def clear_creds():
    for k in ("email", "master_token"):
        try:
            keyring.delete_password(SERVICE, k)
        except Exception:
            pass
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


class LoginDialog(tk.Toplevel):
    """oauth_token ile master token alir (Google sifreyi dogrudan kabul etmiyor)."""

    def __init__(self, master, on_done):
        super().__init__(master)
        self.title("Google Keep'e baglan")
        self.on_done = on_done
        self.resizable(False, False)
        f = ttk.Frame(self, padding=14)
        f.pack()
        steps = ("1) Asagidaki butonla acilan sayfada Google hesabinla giris yap.\n"
                 "2) Giris sonrasi 'Sayfa yuklenemedi / Loading' ekrani kalabilir; normaldir.\n"
                 "3) Tarayicida F12 > Application (Uygulama) > Cookies > accounts.google.com\n"
                 "    icinden 'oauth_token' degerini kopyalayip altaki kutuya yapistir.")
        ttk.Label(f, text=steps, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(f, text="Giris sayfasini ac", command=lambda: webbrowser.open(
            "https://accounts.google.com/EmbeddedSetup")).grid(row=1, column=0, columnspan=2, pady=8)
        ttk.Label(f, text="E-posta:").grid(row=2, column=0, sticky="e")
        self.email = ttk.Entry(f, width=48)
        self.email.grid(row=2, column=1, pady=2)
        ttk.Label(f, text="oauth_token:").grid(row=3, column=0, sticky="e")
        self.tok = ttk.Entry(f, width=48, show="*")
        self.tok.grid(row=3, column=1, pady=2)
        self.status = ttk.Label(f, text="", foreground="#b00020")
        self.status.grid(row=4, column=0, columnspan=2)
        self.btn = ttk.Button(f, text="Baglan", command=self.go)
        self.btn.grid(row=5, column=0, columnspan=2, pady=6)
        self.grab_set()

    def go(self):
        email, tok = self.email.get().strip(), self.tok.get().strip()
        if not email or not tok:
            self.status.config(text="E-posta ve oauth_token gerekli.")
            return
        self.btn.config(state="disabled")
        self.status.config(text="Baglaniliyor...", foreground="#444")

        def work():
            try:
                android_id = secrets.token_hex(8)
                res = gpsoauth.exchange_token(email, tok, android_id)
                mt = res.get("Token")
                if not mt:
                    raise RuntimeError(res.get("Error", "Master token alinamadi"))
                self.after(0, lambda: self.finish(email, mt))
            except Exception as e:
                self.after(0, lambda: (self.status.config(text=f"Hata: {e}", foreground="#b00020"),
                                       self.btn.config(state="normal")))
        threading.Thread(target=work, daemon=True).start()

    def finish(self, email, mt):
        save_creds(email, mt)
        self.destroy()
        self.on_done(email, mt)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KeepWin")
        self.geometry("980x640")
        self.keep = gkeepapi.Keep()
        self.notes = []
        self.current = None
        self.view = "active"  # active | archived | trashed
        self.build_ui()
        email, token = load_creds()
        if email and token:
            self.connect(email, token)
        else:
            self.after(200, lambda: LoginDialog(self, self.connect))

    # ---------- UI ----------
    def build_ui(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="+ Not", command=lambda: self.new(False)).pack(side="left")
        ttk.Button(bar, text="+ Liste", command=lambda: self.new(True)).pack(side="left", padx=4)
        ttk.Button(bar, text="Esitle", command=self.sync).pack(side="left")
        self.viewvar = tk.StringVar(value="Notlar")
        cb = ttk.Combobox(bar, textvariable=self.viewvar, state="readonly", width=10,
                          values=["Notlar", "Arsiv", "Cop"])
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", self.change_view)
        self.q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.q, width=30)
        e.pack(side="right")
        ttk.Label(bar, text="Ara:").pack(side="right")
        self.q.trace_add("write", lambda *_: self.refresh())
        ttk.Button(bar, text="Cikis yap", command=self.logout).pack(side="right", padx=8)

        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw)
        self.lb = tk.Listbox(left, activestyle="none", exportselection=False)
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", self.select)
        pw.add(left, weight=1)

        right = ttk.Frame(pw, padding=8)
        pw.add(right, weight=3)
        self.title_e = ttk.Entry(right, font=("Segoe UI", 14, "bold"))
        self.title_e.pack(fill="x")
        self.body = tk.Text(right, wrap="word", font=("Segoe UI", 11), undo=True)
        self.body.pack(fill="both", expand=True, pady=6)
        self.body.bind("<Double-Button-1>", self.toggle_check)
        row = ttk.Frame(right)
        row.pack(fill="x")
        ttk.Button(row, text="Kaydet", command=self.save).pack(side="left")
        self.pin = ttk.Button(row, text="Sabitle", command=self.toggle_pin)
        self.pin.pack(side="left", padx=4)
        ttk.Button(row, text="Arsivle/Geri al", command=self.toggle_archive).pack(side="left")
        ttk.Button(row, text="Copa at/Geri al", command=self.toggle_trash).pack(side="left", padx=4)
        self.colorvar = tk.StringVar(value="Beyaz")
        c = ttk.Combobox(row, textvariable=self.colorvar, values=list(COLORS), width=9, state="readonly")
        c.pack(side="right")
        c.bind("<<ComboboxSelected>>", self.set_color)
        self.hint = ttk.Label(right, text="", foreground="#666")
        self.hint.pack(anchor="w")
        self.status = ttk.Label(self, text="Hazir", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

    def say(self, t):
        self.status.config(text=t)

    # ---------- Baglanti ----------
    def connect(self, email, token):
        self.say("Baglaniliyor ve notlar indiriliyor...")

        def work():
            try:
                state = None
                if os.path.exists(STATE_FILE):
                    try:
                        state = json.load(open(STATE_FILE, encoding="utf-8"))
                    except Exception:
                        state = None
                self.keep.authenticate(email, token, state=state, sync=True)
                self.after(0, self.after_sync)
            except Exception as e:
                self.after(0, lambda: self.conn_fail(e))
        threading.Thread(target=work, daemon=True).start()

    def conn_fail(self, e):
        self.say(f"Baglanti hatasi: {e}")
        if messagebox.askyesno("Baglanti hatasi", f"{e}\n\nYeniden giris yapmak ister misin?"):
            clear_creds()
            LoginDialog(self, self.connect)

    def after_sync(self):
        try:
            json.dump(self.keep.dump(), open(STATE_FILE, "w", encoding="utf-8"))
        except Exception:
            pass
        self.say("Esitlendi")
        self.refresh()

    def sync(self):
        self.say("Esitleniyor...")

        def work():
            try:
                self.keep.sync()
                self.after(0, self.after_sync)
            except Exception as e:
                self.after(0, lambda: self.say(f"Esitleme hatasi: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def logout(self):
        if messagebox.askyesno("Cikis", "Kayitli oturum silinsin mi?"):
            clear_creds()
            self.keep = gkeepapi.Keep()
            self.notes, self.current = [], None
            self.lb.delete(0, "end")
            LoginDialog(self, self.connect)

    # ---------- Liste ----------
    def change_view(self, _=None):
        self.view = {"Notlar": "active", "Arsiv": "archived", "Cop": "trashed"}[self.viewvar.get()]
        self.refresh()

    def refresh(self):
        q = self.q.get().strip()
        try:
            if q:
                found = list(self.keep.find(query=q))
            else:
                found = list(self.keep.all())
        except Exception:
            found = []
        v = self.view
        def ok(n):
            if v == "trashed":
                return n.trashed
            if n.trashed:
                return False
            return n.archived if v == "archived" else not n.archived
        self.notes = [n for n in found if ok(n)]
        self.notes.sort(key=lambda n: (not n.pinned, -n.timestamps.updated.timestamp()))
        self.lb.delete(0, "end")
        for i, n in enumerate(self.notes):
            is_list = isinstance(n, gkeepapi.node.List)
            label = ("\u2630 " if is_list else "") + ("\U0001F4CC " if n.pinned else "") + (n.title or self.first_line(n) or "(bos)")
            self.lb.insert("end", label)
            self.lb.itemconfig(i, bg=HEX.get(n.color.name, "#ffffff"))

    @staticmethod
    def first_line(n):
        t = (n.text or "").strip().splitlines()
        return t[0][:40] if t else ""

    def select(self, _=None):
        sel = self.lb.curselection()
        if not sel:
            return
        self.current = self.notes[sel[0]]
        self.show(self.current)

    def show(self, n):
        self.title_e.delete(0, "end")
        self.title_e.insert(0, n.title or "")
        self.body.delete("1.0", "end")
        if isinstance(n, gkeepapi.node.List):
            lines = [(CHECKED if i.checked else UNCHECKED) + i.text for i in n.items]
            self.body.insert("1.0", "\n".join(lines))
            self.hint.config(text="Liste: her satir bir madde. Isaretlemek icin satira cift tikla.")
        else:
            self.body.insert("1.0", n.text or "")
            self.hint.config(text="")
        self.pin.config(text="Sabitlemeyi kaldir" if n.pinned else "Sabitle")
        name = next((k for k, c in COLORS.items() if c == n.color), "Beyaz")
        self.colorvar.set(name)

    def toggle_check(self, ev):
        if not isinstance(self.current, gkeepapi.node.List):
            return
        idx = self.body.index(f"@{ev.x},{ev.y}").split(".")[0]
        line = self.body.get(f"{idx}.0", f"{idx}.end")
        if line.startswith(UNCHECKED):
            new = CHECKED + line[len(UNCHECKED):]
        elif line.startswith(CHECKED):
            new = UNCHECKED + line[len(CHECKED):]
        else:
            return
        self.body.delete(f"{idx}.0", f"{idx}.end")
        self.body.insert(f"{idx}.0", new)
        return "break"

    # ---------- Islemler ----------
    def new(self, is_list):
        n = self.keep.createList("", []) if is_list else self.keep.createNote("", "")
        self.current = n
        self.show(n)
        self.title_e.focus_set()

    def save(self):
        n = self.current
        if n is None:
            return
        n.title = self.title_e.get()
        raw = self.body.get("1.0", "end").rstrip("\n")
        if isinstance(n, gkeepapi.node.List):
            for it in list(n.items):
                it.delete()
            for line in raw.splitlines():
                if not line.strip():
                    continue
                if line.startswith(CHECKED):
                    n.add(line[len(CHECKED):], True)
                elif line.startswith(UNCHECKED):
                    n.add(line[len(UNCHECKED):], False)
                else:
                    n.add(line, False)
        else:
            n.text = raw
        self.sync()

    def need(self):
        if self.current is None:
            messagebox.showinfo("KeepWin", "Once bir not sec.")
            return False
        return True

    def toggle_pin(self):
        if self.need():
            self.current.pinned = not self.current.pinned
            self.sync()

    def toggle_archive(self):
        if self.need():
            self.current.archived = not self.current.archived
            self.sync()

    def toggle_trash(self):
        if self.need():
            if self.current.trashed:
                self.current.untrash()
            else:
                self.current.trash()
            self.sync()

    def set_color(self, _=None):
        if self.need():
            self.current.color = COLORS[self.colorvar.get()]
            self.sync()


if __name__ == "__main__":
    App().mainloop()
