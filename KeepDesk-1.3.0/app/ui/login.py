"""Sign-in screen.

Three ways to authenticate, in order of reliability:

1. Browser flow (``accounts.google.com/EmbeddedSetup`` → ``oauth_token`` cookie)
   — the method gpsoauth documents for accounts where the legacy password
   login answers ``BadAuthentication``.
2. App password (legacy master login) — kept as a fallback.
3. Master token paste — for people who already have one.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from .. import theme
from ..service import AuthError, ServiceError
from . import icons
from .widgets import CheckToggle, center_on_parent

APP_PASSWORDS_URL = "https://myaccount.google.com/apppasswords"
SECURITY_URL = "https://myaccount.google.com/security"
EMBEDDED_SETUP_URL = "https://accounts.google.com/EmbeddedSetup"


def _link(master, text: str, command, bg: str = theme.SURFACE,
          color: str = "#8A6A13") -> tk.Label:
    label = tk.Label(master, text=text, bg=bg, fg=color,
                     font=theme.font(theme._SIZE_SMALL, "bold"), cursor="hand2")
    label.bind("<Button-1>", lambda _e: command())
    label.bind("<Enter>", lambda _e: label.configure(fg=theme.ACCENT_HOVER))
    label.bind("<Leave>", lambda _e: label.configure(fg=color))
    return label


class _Dialog(tk.Toplevel):
    def __init__(self, master, title: str, width: int = 620) -> None:
        super().__init__(master)
        self.title(title)
        self.configure(bg=theme.SURFACE)
        self.resizable(False, False)
        self.transient(master)
        self._width = width

    def finish(self) -> None:
        self.update_idletasks()
        center_on_parent(self, self.master, self._width, self.winfo_reqheight())
        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _e: self.destroy())


class TokenHelpDialog(_Dialog):
    STEPS = [
        ("1", "Google giriş sayfasını açın.",
         "Aşağıdaki düğme sizi accounts.google.com/EmbeddedSetup adresine götürür. "
         "KeepDesk'in kendi penceresi değil, normal tarayıcınız açılır."),
        ("2", "Hesabınızla giriş yapın ve \"Kabul ediyorum\"a basın.",
         "Ardından sayfa boş görünebilir ya da sürekli yükleniyor gibi kalabilir. "
         "Bu normaldir; sayfayı kapatmayın."),
        ("3", "Adres çubuğundaki kilit simgesine tıklayın.",
         "Chrome/Edge: kilit simgesi → \"Çerezler ve site verileri\" → \"Yönet\" → "
         "accounts.google.com → oauth_token."),
        ("4", "oauth_token satırındaki değeri kopyalayın.",
         "Değer oauth2_4/ ile başlar ve oldukça uzundur. \"İçerik\" alanındaki "
         "metnin tamamını kopyalayın."),
        ("5", "KeepDesk'e yapıştırıp \"Kodu doğrula ve bağlan\"a basın.",
         "Kod tek kullanımlıktır ve kısa süre geçerlidir. Hata alırsanız "
         "tarayıcıda sayfayı yenileyip yeni bir kod alın."),
    ]

    def __init__(self, master) -> None:
        super().__init__(master, "Tarayıcı ile giriş — adım adım")
        wrap = tk.Frame(self, bg=theme.SURFACE, padx=26, pady=22)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Tarayıcı ile giriş", bg=theme.SURFACE, fg=theme.TEXT,
                 font=theme.font(16, "bold")).pack(anchor="w")
        tk.Label(
            wrap,
            text=("Google, bu hesaplarda uygulama şifresiyle yapılan girişleri reddettiği için "
                  "tarayıcıdan alınan tek kullanımlık bir kod kullanıyoruz. Kod, hesabınıza "
                  "KeepDesk'in erişmesini sağlayan kalıcı bir anahtara dönüştürülür."),
            bg=theme.SURFACE, fg=theme.MUTED, justify="left", wraplength=540,
            font=theme.font(theme._SIZE_BASE),
        ).pack(anchor="w", pady=(6, 14))

        for number, title, detail in self.STEPS:
            row = tk.Frame(wrap, bg=theme.SURFACE)
            row.pack(fill="x", pady=5)
            badge = tk.Canvas(row, width=24, height=24, bg=theme.SURFACE,
                              highlightthickness=0, bd=0)
            badge.pack(side="left", anchor="n")
            badge.create_oval(1, 1, 23, 23, fill=theme.ACCENT_TINT, outline="")
            badge.create_text(12, 12, text=number, fill=theme.ACCENT_TEXT,
                              font=theme.font(theme._SIZE_SMALL, "bold"))
            col = tk.Frame(row, bg=theme.SURFACE)
            col.pack(side="left", fill="x", expand=True, padx=(10, 0))
            tk.Label(col, text=title, bg=theme.SURFACE, fg=theme.TEXT,
                     font=theme.font(theme._SIZE_BASE, "bold"), justify="left",
                     wraplength=490).pack(anchor="w")
            tk.Label(col, text=detail, bg=theme.SURFACE, fg=theme.MUTED,
                     font=theme.font(theme._SIZE_SMALL), justify="left",
                     wraplength=490).pack(anchor="w")

        footer = tk.Frame(wrap, bg=theme.SURFACE)
        footer.pack(fill="x", pady=(18, 0))
        ttk.Button(footer, text="Google giriş sayfasını aç", style="Accent.TButton",
                   command=lambda: webbrowser.open(EMBEDDED_SETUP_URL)).pack(side="left")
        ttk.Button(footer, text="Kapat", command=self.destroy).pack(side="right")
        self.finish()


class AppPasswordDialog(_Dialog):
    STEPS = [
        ("1", "Google Hesabınızda 2 Adımlı Doğrulamayı açın.",
         "myaccount.google.com/security → \"2 Adımlı Doğrulama\""),
        ("2", "Uygulama şifreleri sayfasını açın.",
         "Arama çubuğuna \"Uygulama şifreleri\" yazın veya alttaki düğmeyi kullanın."),
        ("3", "Yeni bir uygulama şifresi oluşturun.",
         "Uygulama: \"Diğer (özel ad)\" → ad olarak KeepDesk yazın → Oluştur."),
        ("4", "16 haneli şifreyi kopyalayıp giriş ekranına yapıştırın.",
         "Boşluklar önemli değil; KeepDesk şifreyi olduğu gibi kabul eder."),
    ]

    def __init__(self, master) -> None:
        super().__init__(master, "Uygulama şifresi nasıl alınır?")
        wrap = tk.Frame(self, bg=theme.SURFACE, padx=26, pady=22)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Google uygulama şifresi", bg=theme.SURFACE, fg=theme.TEXT,
                 font=theme.font(16, "bold")).pack(anchor="w")
        tk.Label(
            wrap,
            text=("Google, üçüncü taraf uygulamaların normal hesap şifresiyle giriş yapmasına izin vermiyor.\n"
                  "Uygulama şifresi 16 hanelidir ve yalnızca KeepDesk'e erişim verir.\n"
                  "Not: Google bu yöntemi de giderek daha sık reddediyor; olmazsa "
                  "\"Tarayıcı ile giriş\" sekmesini kullanın."),
            bg=theme.SURFACE, fg=theme.MUTED, justify="left",
            font=theme.font(theme._SIZE_BASE), wraplength=540,
        ).pack(anchor="w", pady=(6, 16))

        for number, title, detail in self.STEPS:
            row = tk.Frame(wrap, bg=theme.SURFACE)
            row.pack(fill="x", pady=5)
            badge = tk.Canvas(row, width=24, height=24, bg=theme.SURFACE,
                              highlightthickness=0, bd=0)
            badge.pack(side="left", anchor="n")
            badge.create_oval(1, 1, 23, 23, fill=theme.ACCENT_TINT, outline="")
            badge.create_text(12, 12, text=number, fill=theme.ACCENT_TEXT,
                              font=theme.font(theme._SIZE_SMALL, "bold"))
            col = tk.Frame(row, bg=theme.SURFACE)
            col.pack(side="left", fill="x", expand=True, padx=(10, 0))
            tk.Label(col, text=title, bg=theme.SURFACE, fg=theme.TEXT,
                     font=theme.font(theme._SIZE_BASE, "bold"), justify="left",
                     wraplength=490).pack(anchor="w")
            tk.Label(col, text=detail, bg=theme.SURFACE, fg=theme.MUTED,
                     font=theme.font(theme._SIZE_SMALL), justify="left",
                     wraplength=490).pack(anchor="w")

        footer = tk.Frame(wrap, bg=theme.SURFACE)
        footer.pack(fill="x", pady=(18, 0))
        ttk.Button(footer, text="Şifre sayfasını aç", style="Accent.TButton",
                   command=lambda: webbrowser.open(APP_PASSWORDS_URL)).pack(side="left")
        ttk.Button(footer, text="Kapat", command=self.destroy).pack(side="right")
        self.finish()


class LoginView(tk.Frame):
    MODES = [
        ("browser", "Tarayıcı ile giriş"),
        ("password", "Uygulama şifresi"),
        ("token", "Master token"),
    ]

    def __init__(self, master, service, on_success, on_notice) -> None:
        super().__init__(master, bg=theme.BG)
        self.service = service
        self.on_success = on_success
        self.on_notice = on_notice
        self._busy = False
        self._mode = "browser"
        self._tab_labels: dict[str, tk.Label] = {}
        self._secret_widget = None

        outer = tk.Frame(self, bg=theme.BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(outer, bg=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.BORDER, padx=38, pady=30)
        card.pack()
        self._card = card

        logo = tk.Canvas(card, width=52, height=52, bg=theme.SURFACE,
                         highlightthickness=0, bd=0)
        logo.pack(anchor="w")
        logo.create_rectangle(4, 4, 48, 48, fill=theme.ACCENT, outline="")
        for i, wdt in enumerate((30, 30, 20)):
            logo.create_line(12, 17 + i * 9, 12 + wdt, 17 + i * 9,
                             fill=theme.ACCENT_TEXT, width=3, capstyle="round")

        tk.Label(card, text="KeepDesk", bg=theme.SURFACE, fg=theme.TEXT,
                 font=theme.font(22, "bold")).pack(anchor="w", pady=(12, 0))
        tk.Label(card, text="Google Keep hesabınıza bağlanın", bg=theme.SURFACE,
                 fg=theme.MUTED, font=theme.font(theme._SIZE_BASE)).pack(anchor="w", pady=(2, 16))

        # mode tabs -----------------------------------------------------
        tabs = tk.Frame(card, bg=theme.SURFACE)
        tabs.pack(fill="x")
        for key, label in self.MODES:
            lbl = tk.Label(tabs, text=label, bg=theme.SURFACE, fg=theme.MUTED,
                           font=theme.font(theme._SIZE_SMALL), cursor="hand2", padx=2)
            lbl.pack(side="left", padx=(0, 14))
            lbl.bind("<Button-1>", lambda _e, k=key: self.set_mode(k))
            lbl.bind("<Configure>", lambda _e: self._draw_tab_line())
            self._tab_labels[key] = lbl
        self._tabs = tabs
        self._tab_line = tk.Canvas(card, height=2, bg=theme.SURFACE,
                                   highlightthickness=0, bd=0)
        self._tab_line.pack(fill="x", pady=(4, 14))

        email_row = tk.Frame(card, bg=theme.SURFACE)
        email_row.pack(fill="x")
        tk.Label(email_row, text="E-posta", bg=theme.SURFACE, fg=theme.TEXT_SOFT,
                 font=theme.font(theme._SIZE_SMALL, "bold")).pack(anchor="w")
        self.email_var = tk.StringVar()
        self.email_entry = ttk.Entry(email_row, textvariable=self.email_var, width=44)
        self.email_entry.pack(fill="x", pady=(4, 12), ipady=1)

        self.secret_var = tk.StringVar()
        self.content = tk.Frame(card, bg=theme.SURFACE)
        self.content.pack(fill="x")

        opts = tk.Frame(card, bg=theme.SURFACE)
        opts.pack(fill="x", pady=(10, 12))
        self.remember_var = tk.BooleanVar(value=True)
        self.remember = CheckToggle(opts, "Bu cihazda oturumu açık tut",
                                    variable=self.remember_var)
        self.remember.pack(anchor="w")

        self.submit = ttk.Button(card, text="Giriş yap", style="Accent.TButton",
                                 command=self._submit)
        self.submit.pack(fill="x", pady=(0, 0), ipady=3)

        self.message = tk.Label(card, text="", bg=theme.SURFACE, fg=theme.RED,
                                font=theme.font(theme._SIZE_SMALL), justify="left",
                                wraplength=400)
        self.message.pack(anchor="w", pady=(12, 0))

        tk.Label(
            card,
            text=("Not: KeepDesk, Google'ın resmî olmayan Keep API'sini kullanır. "
                  "Oturum anahtarı yalnızca bu bilgisayarda, Windows DPAPI ile şifrelenmiş "
                  "olarak saklanır; Google şifreniz hiçbir zaman kaydedilmez."),
            bg=theme.SURFACE, fg=theme.FAINT, font=theme.font(8), justify="left",
            wraplength=400,
        ).pack(anchor="w", pady=(6, 0))

        self.email_entry.bind("<Return>", lambda _e: self._focus_secret())
        self.after(150, self.email_entry.focus_set)
        self.set_mode("browser")
        self.after(120, self._draw_tab_line)

    # -- mode switching ---------------------------------------------------
    def _draw_tab_line(self) -> None:
        if not hasattr(self, "_tab_line"):
            return
        self._tab_line.delete("all")
        label = self._tab_labels.get(self._mode)
        if label is None or not label.winfo_exists():
            return
        x, width = label.winfo_x(), label.winfo_width()
        if width > 1:
            # tabs and the underline share the same parent, so x maps directly
            self._tab_line.create_line(x, 1, x + width, 1, fill=theme.ACCENT, width=2)

    def _focus_secret(self) -> None:
        widget = self._secret_widget
        if widget is not None:
            try:
                widget.focus_set()
            except tk.TclError:
                pass

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        for key, label in self._tab_labels.items():
            active = key == mode
            label.configure(fg=theme.TEXT if active else theme.MUTED,
                            font=theme.font(theme._SIZE_SMALL, "bold" if active else "normal"))
        for child in self.content.winfo_children():
            child.destroy()
        self._secret_widget = None
        self.message.configure(text="")

        if mode == "browser":
            self._build_browser()
            self.submit.configure(text="Kodu doğrula ve bağlan")
        elif mode == "password":
            self._build_password()
            self.submit.configure(text="Giriş yap")
        else:
            self._build_token()
            self.submit.configure(text="Giriş yap")
        self.after(40, self._draw_tab_line)

    def _build_browser(self) -> None:
        tk.Label(
            self.content,
            text=("Google, uygulama şifresiyle yapılan girişi bu hesapta reddediyor. "
                  "Aşağıdaki düğmeyle tarayıcıda giriş yapıp aldığınız tek kullanımlık kodu "
                  "buraya yapıştırın; KeepDesk onu kalıcı bir anahtara çevirir."),
            bg=theme.SURFACE, fg=theme.MUTED, justify="left", wraplength=400,
            font=theme.font(theme._SIZE_SMALL),
        ).pack(anchor="w")

        row = tk.Frame(self.content, bg=theme.SURFACE)
        row.pack(fill="x", pady=(10, 10))
        ttk.Button(row, text="1)  Google giriş sayfasını aç",
                   command=lambda: webbrowser.open(EMBEDDED_SETUP_URL)).pack(side="left")
        _link(row, "Adım adım anlatım", self._show_token_help).pack(side="left", padx=(12, 0))

        tk.Label(self.content, text="2)  Kopyaladığınız oauth_token kodu",
                 bg=theme.SURFACE, fg=theme.TEXT_SOFT,
                 font=theme.font(theme._SIZE_SMALL, "bold")).pack(anchor="w")
        self.token_entry = ttk.Entry(self.content, textvariable=self.secret_var, width=44)
        self.token_entry.pack(fill="x", pady=(4, 0), ipady=1)
        self.token_entry.bind("<Return>", lambda _e: self._submit())
        self._secret_widget = self.token_entry
        tk.Label(self.content, text="Kod oauth2_4/ ile başlar ve kısa süre geçerlidir.",
                 bg=theme.SURFACE, fg=theme.FAINT, font=theme.font(8)).pack(anchor="w", pady=(4, 0))

    def _build_password(self) -> None:
        tk.Label(self.content, text="Uygulama şifresi (16 hane)", bg=theme.SURFACE,
                 fg=theme.TEXT_SOFT, font=theme.font(theme._SIZE_SMALL, "bold")).pack(anchor="w")
        self.password_entry = ttk.Entry(self.content, textvariable=self.secret_var,
                                        show="•", width=44)
        self.password_entry.pack(fill="x", pady=(4, 4), ipady=1)
        self.password_entry.bind("<Return>", lambda _e: self._submit())
        self._secret_widget = self.password_entry
        row = tk.Frame(self.content, bg=theme.SURFACE)
        row.pack(fill="x", pady=(2, 0))
        _link(row, "Uygulama şifresi nasıl alınır?", self._show_app_help).pack(side="left")
        tk.Label(self.content, text="Google bu yöntemi reddederse tarayıcı ile girişi deneyin.",
                 bg=theme.SURFACE, fg=theme.FAINT, font=theme.font(8)).pack(anchor="w", pady=(4, 0))

    def _build_token(self) -> None:
        tk.Label(self.content, text="Master token (aas_et/…)", bg=theme.SURFACE,
                 fg=theme.TEXT_SOFT, font=theme.font(theme._SIZE_SMALL, "bold")).pack(anchor="w")
        self.token_paste = ttk.Entry(self.content, textvariable=self.secret_var, width=44)
        self.token_paste.pack(fill="x", pady=(4, 0), ipady=1)
        self.token_paste.bind("<Return>", lambda _e: self._submit())
        self._secret_widget = self.token_paste
        tk.Label(self.content,
                 text="Başka bir araçla (gkeepapi/gpsoauth) ürettiğiniz uzun ömürlü anahtar.",
                 bg=theme.SURFACE, fg=theme.FAINT, font=theme.font(8)).pack(anchor="w", pady=(4, 0))

    # -- dialogs ----------------------------------------------------------
    def _show_token_help(self) -> None:
        TokenHelpDialog(self.winfo_toplevel())

    def _show_app_help(self) -> None:
        AppPasswordDialog(self.winfo_toplevel())

    # -- submit -------------------------------------------------------------
    def prefill(self, email: str) -> None:
        if email:
            self.email_var.set(email)

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.submit.configure(state=state, text=text or self._default_button_text())
        self.email_entry.configure(state=state)
        if self._secret_widget is not None:
            self._secret_widget.configure(state=state)

    def _default_button_text(self) -> str:
        return {
            "browser": "Kodu doğrula ve bağlan",
            "password": "Giriş yap",
            "token": "Giriş yap",
        }.get(self._mode, "Giriş yap")

    def _submit(self) -> None:
        if self._busy:
            return
        email = self.email_var.get().strip()
        secret = self.secret_var.get().strip()
        self.message.configure(text="")
        if "@" not in email:
            self.message.configure(text="Geçerli bir e-posta adresi girin.")
            self.email_entry.focus_set()
            return
        if not secret:
            self.message.configure(
                text={"browser": "Tarayıcıdan aldığınız kodu yapıştırın.",
                      "password": "Uygulama şifresini girin.",
                      "token": "Master token girin."}[self._mode])
            self._focus_secret()
            return

        self._set_busy(True, "Bağlanıyor…")
        remember = self.remember_var.get()

        def done(result, error):
            self._done(result, error, remember)

        if self._mode == "browser":
            self.service.login_with_oauth_token(email, "".join(secret.split()), done)
        elif self._mode == "password":
            compact = "".join(secret.split())
            self.service.login(email, compact if len(compact) == 16 else secret, done)
        else:
            self.service.resume(email, secret, done)

    def _done(self, result, error, remember: bool) -> None:
        self._set_busy(False)
        if error is not None:
            if isinstance(error, (AuthError, ServiceError)):
                text = str(error)
            else:
                text = f"Beklenmeyen hata: {error}"
            self.message.configure(text=text)
            self.secret_var.set("")
            self._focus_secret()
            return
        self.on_success(result.get("email", ""), result.get("token", ""), remember)
