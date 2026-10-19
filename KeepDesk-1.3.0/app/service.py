"""All Google Keep access lives here, on a single background worker thread.

gkeepapi is not thread safe, so every call touches the ``Keep`` instance only
from ``_worker_loop``.  The UI submits callables with :meth:`KeepService.call`
and receives results back on the Tk main loop through ``schedule``.
"""

from __future__ import annotations

import logging
import queue
import secrets
import threading
import time
from typing import Any, Callable

import gkeepapi
import gpsoauth
from gkeepapi import exception as gexc
from gkeepapi.node import ColorValue, List as KeepList

from .store import save_cache

log = logging.getLogger("keepdesk.service")

Callback = Callable[[Any, BaseException | None], None] | None


class AuthError(Exception):
    """Human readable authentication failure."""


class ServiceError(Exception):
    """Generic, human readable service failure."""


def _auth_message(payload: dict) -> str:
    code = str(payload.get("Error") or "")
    detail = str(payload.get("ErrorDetail") or "")
    if code == "NeedsBrowser":
        return (
            "Google bu giriş için tarayıcı doğrulaması istedi.\n"
            "Lütfen normal şifre yerine bir uygulama şifresi kullanın."
        )
    if code == "BadAuthentication":
        return (
            "Google bu giriş bilgilerini kabul etmedi.\n"
            "• Normal hesap şifresi çalışmaz; 16 haneli UYGULAMA ŞİFRESİ gerekir.\n"
            "• 2 Adımlı Doğrulama kapalıysa önce onu açın, sonra "
            "myaccount.google.com/apppasswords adresinden KeepDesk için şifre oluşturun.\n"
            "• Şifreyi kopyalarken araya boşluk girmişse sorun olmaz, yine de birkaç dakika "
            "sonra tekrar deneyin."
        )
    if code in {"NotVerified", "TermsNotAgreed", "ServiceDisabled"}:
        return "Hesap doğrulanmamış veya bu giriş yöntemi kapalı. Google hesap ayarlarınızı kontrol edin."
    if code == "CaptchaRequired":
        return "Google ek doğrulama istedi. Tarayıcıdan hesabınıza girip tekrar deneyin."
    if detail:
        return f"Giriş başarısız: {code} ({detail})"
    return f"Giriş başarısız: {code or 'bilinmeyen hata'}"


class KeepService:
    """Threaded facade over gkeepapi."""

    PERIODIC_SYNC = 60.0
    DEBOUNCE = 1.2

    def __init__(
        self,
        schedule: Callable[[Callable[[], None]], None],
        device_id: str = "",
    ) -> None:
        self._schedule = schedule
        self.device_id = device_id or secrets.token_hex(8)
        self._queue: queue.Queue = queue.Queue()
        self._stop = False
        self._thread = threading.Thread(target=self._worker_loop, name="keep-worker", daemon=True)
        self._thread.start()

        self.keep = gkeepapi.Keep()
        self.connected = False
        self.email = ""
        self.status = "offline"  # offline | syncing | ok | error | auth
        self.last_sync = 0.0
        self.last_error = ""

        self._notes: dict[str, dict] = {}
        self._labels: list[dict] = []
        self._pending_sync_at: float | None = None
        self._syncing = False
        self._next_periodic = 0.0

        # UI callbacks (assigned by the app shell).
        self.on_update: Callable[[], None] | None = None
        self.on_status: Callable[[str], None] | None = None
        self.on_auth_lost: Callable[[str], None] | None = None

    # -- plumbing -------------------------------------------------------
    def call(self, job: Callable[[], Any], on_done: Callback = None) -> None:
        self._queue.put((job, on_done))

    def shutdown(self) -> None:
        self._stop = True
        self._queue.put((None, None))

    def _deliver(self, cb: Callback, result: Any, error: BaseException | None) -> None:
        if cb is None:
            return
        try:
            self._schedule(lambda: cb(result, error))
        except Exception:  # pragma: no cover - window teardown races
            log.debug("callback dropped", exc_info=True)

    def _worker_loop(self) -> None:
        while not self._stop:
            try:
                item = self._queue.get(timeout=0.35)
            except queue.Empty:
                item = None
            if item is not None:
                job, cb = item
                if job is None:
                    break
                result: Any = None
                error: BaseException | None = None
                try:
                    result = job()
                except BaseException as exc:  # noqa: BLE001 - forwarded to UI
                    error = exc
                self._deliver(cb, result, error)
            self._tick()

    def _tick(self) -> None:
        if not self.connected or self._syncing:
            return
        now = time.time()
        if self._pending_sync_at is not None and now >= self._pending_sync_at:
            self._pending_sync_at = None
            self._run_sync()
        elif now >= self._next_periodic:
            self._next_periodic = now + self.PERIODIC_SYNC
            self._run_sync(silent=True)

    # -- status ---------------------------------------------------------
    def _set_status(self, status: str, message: str = "") -> None:
        self.status = status
        if message:
            self.last_error = message
        cb = self.on_status
        if cb:
            try:
                self._schedule(lambda: cb(status))
            except Exception:
                pass

    # -- snapshots ------------------------------------------------------
    def _snapshot(self, node) -> dict | None:
        try:
            is_list = isinstance(node, KeepList)
            items: list[dict] = []
            if is_list:
                items = [
                    {"id": item.id, "text": item.text, "checked": bool(item.checked)}
                    for item in node.items
                    if not item.deleted
                ]
            labels = [label.name for label in node.labels.all()]
            updated = node.timestamps.updated or node.timestamps.created
            created = node.timestamps.created
            return {
                "id": node.id,
                "server_id": node.server_id,
                "kind": "list" if is_list else "note",
                "title": node.title or "",
                "text": "" if is_list else (node.text or ""),
                "items": items,
                "labels": labels,
                "color": node.color.value if node.color else "DEFAULT",
                "pinned": bool(node.pinned),
                "archived": bool(node.archived),
                "trashed": bool(node.trashed),
                "updated": updated.timestamp() if updated else 0.0,
                "created": created.timestamp() if created else 0.0,
            }
        except Exception:  # pragma: no cover - malformed node
            log.warning("could not snapshot node %s", getattr(node, "id", "?"), exc_info=True)
            return None

    def _rebuild(self) -> None:
        notes: dict[str, dict] = {}
        for node in self.keep.all():
            if node.deleted:
                continue
            snap = self._snapshot(node)
            if snap:
                notes[snap["id"]] = snap
        self._notes = notes
        self._labels = sorted(
            ({"id": label.id, "name": label.name} for label in self.keep.labels()),
            key=lambda item: item["name"].casefold(),
        )

    def _notify(self) -> None:
        cb = self.on_update
        if cb:
            try:
                self._schedule(cb)
            except Exception:
                pass

    def _persist(self) -> None:
        try:
            save_cache(
                {
                    "saved_at": time.time(),
                    "email": self.email,
                    "notes": list(self._notes.values()),
                    "labels": self._labels,
                }
            )
        except Exception:  # pragma: no cover
            log.debug("cache write failed", exc_info=True)

    def _after_edit(self, delay: float | None = None) -> None:
        self._rebuild()
        self._notify()
        self._persist()
        self._pending_sync_at = time.time() + (self.DEBOUNCE if delay is None else delay)

    # -- cache access for the UI ---------------------------------------
    def cached_notes(self) -> list[dict]:
        return list(self._notes.values())

    def cached_labels(self) -> list[dict]:
        return list(self._labels)

    def note(self, note_id: str) -> dict | None:
        return self._notes.get(note_id)

    def prime_cache(self, payload: dict) -> None:
        """Load the offline snapshot so the board renders before the first sync."""
        notes: dict[str, dict] = {}
        for note in payload.get("notes") or []:
            if isinstance(note, dict) and note.get("id"):
                notes[note["id"]] = note
        self._notes = notes
        self._labels = [item for item in payload.get("labels") or [] if isinstance(item, dict)]
        if payload.get("email"):
            self.email = str(payload["email"])
        log.info("primed cache with %d notes", len(notes))

    # -- login ----------------------------------------------------------
    def _master_login(self, email: str, app_password: str, device_id: str) -> str:
        # Google shows app passwords as "abcd efgh ijkl mnop"; the actual secret
        # has no spaces, and passing them verbatim yields BadAuthentication.
        compact = "".join(app_password.split())
        password = compact if len(compact) == 16 else app_password

        last_error: Exception | None = None
        # A mismatching device country occasionally trips Google's risk checks,
        # so retry once with the local country before giving up.
        for country in ("us", "tr"):
            try:
                payload = gpsoauth.perform_master_login(
                    email.strip(), password, device_id,
                    device_country=country, operator_country=country, lang="tr",
                )
            except Exception as exc:  # network/TLS failure
                raise ServiceError(
                    "Google'a bağlanılamadı. İnternet bağlantınızı ve varsa proxy/VPN "
                    f"ayarlarınızı kontrol edin.\n({type(exc).__name__}: {exc})"
                ) from exc
            if "Token" in payload:
                return str(payload["Token"])
            last_error = AuthError(_auth_message(payload))
            if str(payload.get("Error") or "") != "BadAuthentication":
                break  # only retry on the generic rejection
        raise last_error or AuthError("Giriş başarısız.")

    def _open_session(self, email: str, token: str) -> None:
        keep = gkeepapi.Keep()
        try:
            keep.authenticate(email, token, sync=False, device_id=self.device_id)
        except gexc.BrowserLoginRequiredException as exc:
            raise AuthError(_auth_message({"Error": "NeedsBrowser", "Url": exc.url})) from exc
        except gexc.LoginException as exc:
            raise AuthError(f"Oturum açılamadı: {exc}") from exc
        except Exception as exc:
            raise ServiceError(f"Oturum açılamadı: {exc}") from exc
        self.keep = keep
        log.info("session opened for %s", email)

    def login(self, email: str, app_password: str, on_done: Callback = None) -> None:
        email = email.strip()

        def job() -> dict:
            token = self._master_login(email, app_password, self.device_id)
            self._open_session(email, token)
            self.email = email
            self.connected = True
            self._run_sync(first=True)
            if not self.connected:
                raise ServiceError(self.last_error or "İlk senkronizasyon başarısız oldu.")
            return {"email": email, "token": token}

        self.call(job, on_done)

    def resume(self, email: str, token: str, on_done: Callback = None) -> None:
        def job() -> dict:
            self._open_session(email, token)
            self.email = email
            self.connected = True
            self._run_sync(first=True)
            return {"email": email, "token": token}

        self.call(job, on_done)

    def login_with_oauth_token(self, email: str, oauth_token: str,
                               on_done: Callback = None) -> None:
        """Exchange the browser ``oauth_token`` (oauth2_4/...) for a master token."""
        email = email.strip()
        token = oauth_token.strip().strip("\"'")
        if "oauth_token=" in token:
            token = token.split("oauth_token=", 1)[1].strip().strip("\"'")

        def job() -> dict:
            # Someone may paste a master token into this box; accept that too.
            if token.startswith("aas_et/"):
                self._open_session(email, token)
                self.email = email
                self.connected = True
                self._run_sync(first=True)
                return {"email": email, "token": token}

            try:
                payload = gpsoauth.exchange_token(email, token, self.device_id)
            except Exception as exc:  # network/TLS failure
                raise ServiceError(
                    "Google'a bağlanılamadı. İnternet bağlantınızı kontrol edin.\n"
                    f"({type(exc).__name__}: {exc})"
                ) from exc
            if "Token" not in payload:
                log.warning("oauth_token exchange rejected: %s",
                            {k: v for k, v in payload.items() if k != "Token"})
                raise AuthError(
                    "Bu kod kabul edilmedi.\n"
                    "Kod tek kullanımlıktır ve kısa süre geçerlidir. "
                    "Google sayfasını yenileyip YENİ bir oauth_token kopyalayın "
                    "(oauth2_4/ ile başlar)."
                )
            master = str(payload["Token"])
            self._open_session(email, master)
            self.email = email
            self.connected = True
            self._run_sync(first=True)
            return {"email": email, "token": master}

        self.call(job, on_done)

    def logout(self) -> None:
        def job() -> None:
            self.connected = False
            self.keep = gkeepapi.Keep()
            self.email = ""
            self._notes = {}
            self._labels = []
            self.status = "offline"

        self.call(job, None)

    # -- sync -----------------------------------------------------------
    def request_sync(self, delay: float = 0.0) -> None:
        when = time.time() + delay
        if self._pending_sync_at is None or when < self._pending_sync_at:
            self._pending_sync_at = when

    def _run_sync(self, first: bool = False, silent: bool = False) -> None:
        if not self.connected:
            return
        if self._syncing:
            self.request_sync(1.0)
            return
        self._syncing = True
        if not silent or first:
            self._set_status("syncing")
        try:
            try:
                self.keep.sync()
            except gexc.ResyncRequiredException:
                log.warning("server requested a full resync")
                self.keep.sync(resync=True)
            except gexc.UpgradeRecommendedException:
                log.warning("server requested upgrade; continuing")
                self.keep.sync(resync=True)
            self.last_sync = time.time()
            self._rebuild()
            self._persist()
            self._set_status("ok")
            self._next_periodic = time.time() + self.PERIODIC_SYNC
        except gexc.APIException as exc:
            if getattr(exc, "code", None) == 401:
                self.connected = False
                self._set_status("auth")
                cb = self.on_auth_lost
                if cb:
                    try:
                        self._schedule(lambda: cb("Oturum süresi doldu, yeniden giriş yapın."))
                    except Exception:
                        pass
            else:
                self._set_status("error", str(exc))
                self._pending_sync_at = time.time() + 20
                log.warning("sync API error: %s", exc)
        except gexc.LoginException as exc:
            self.connected = False
            self._set_status("auth")
            log.warning("sync login error: %s", exc)
        except Exception as exc:  # noqa: BLE001 - network problems
            self._set_status("error", str(exc))
            self._pending_sync_at = time.time() + 20
            log.warning("sync failed: %s", exc)
        finally:
            self._syncing = False
            self._notify()

    # -- mutations ------------------------------------------------------
    def _node(self, note_id: str):
        node = self.keep.get(note_id)
        if node is None:
            raise ServiceError("Not bulunamadı (başka bir cihazda silinmiş olabilir).")
        return node

    def create_note(self, kind: str, title: str, text: str, on_done: Callback = None) -> None:
        def job() -> dict:
            if kind == "list":
                node = self.keep.createList(title or "", [])
            else:
                node = self.keep.createNote(title or "", text or "")
            self._after_edit(delay=0.2)
            return self._snapshot(node) or {}

        self.call(job, on_done)

    def update(self, note_id: str, patch: dict, on_done: Callback = None) -> None:
        def job() -> dict:
            node = self._node(note_id)
            if "title" in patch and node.title != patch["title"]:
                node.title = patch["title"]
            if "text" in patch and not isinstance(node, KeepList):
                if node.text != patch["text"]:
                    node.text = patch["text"]
            if "color" in patch:
                try:
                    node.color = ColorValue(patch["color"])
                except ValueError:
                    pass
            if "pinned" in patch and bool(node.pinned) != bool(patch["pinned"]):
                node.pinned = bool(patch["pinned"])
            if "archived" in patch and bool(node.archived) != bool(patch["archived"]):
                node.archived = bool(patch["archived"])
            self._after_edit()
            return self._snapshot(node) or {}

        self.call(job, on_done)

    def set_items(self, note_id: str, items: list[dict], on_done: Callback = None) -> None:
        """Replace the checklist of a list node (matched by item id)."""

        def job() -> dict:
            node = self._node(note_id)
            if not isinstance(node, KeepList):
                raise ServiceError("Bu not bir kontrol listesi değil.")
            existing = {item.id: item for item in node.items}
            keep_ids = set()
            for item in items:
                item_id = item.get("id") or ""
                text = item.get("text", "")
                checked = bool(item.get("checked"))
                current = existing.get(item_id)
                if current is None:
                    node.add(text, checked)
                else:
                    keep_ids.add(item_id)
                    if current.text != text:
                        current.text = text
                    if bool(current.checked) != checked:
                        current.checked = checked
            for item_id, current in existing.items():
                if item_id not in keep_ids:
                    current.delete()
            self._after_edit()
            return self._snapshot(node) or {}

        self.call(job, on_done)

    def trash(self, note_id: str, on_done: Callback = None) -> None:
        self._flag(note_id, "trash", on_done)

    def untrash(self, note_id: str, on_done: Callback = None) -> None:
        self._flag(note_id, "untrash", on_done)

    def delete_forever(self, note_id: str, on_done: Callback = None) -> None:
        self._flag(note_id, "delete", on_done)

    def _flag(self, note_id: str, action: str, on_done: Callback) -> None:
        def job() -> dict | None:
            node = self._node(note_id)
            if action == "trash":
                node.trash()
            elif action == "untrash":
                node.untrash()
            elif action == "delete":
                node.delete()
            self._after_edit(delay=0.3)
            return self._snapshot(node)

        self.call(job, on_done)

    def empty_trash(self, on_done: Callback = None) -> None:
        def job() -> int:
            count = 0
            for node in list(self.keep.find(trashed=True)):
                node.delete()
                count += 1
            self._after_edit(delay=0.3)
            return count

        self.call(job, on_done)

    def set_labels(self, note_id: str, names: list[str], on_done: Callback = None) -> None:
        def job() -> dict:
            node = self._node(note_id)
            wanted = {name.casefold(): name for name in names if name.strip()}
            current = {label.name.casefold(): label for label in node.labels.all()}
            for key, label in current.items():
                if key not in wanted:
                    node.labels.remove(label)
            for key, name in wanted.items():
                if key not in current:
                    label = self.keep.findLabel(name, create=True)
                    if label:
                        node.labels.add(label)
            node.touch(True)
            self._after_edit()
            return self._snapshot(node) or {}

        self.call(job, on_done)

    def create_label(self, name: str, on_done: Callback = None) -> None:
        def job() -> dict:
            name = name.strip()
            if not name:
                raise ServiceError("Etiket adı boş olamaz.")
            label = self.keep.findLabel(name)
            if label is None:
                label = self.keep.createLabel(name)
            self._after_edit(delay=0.4)
            return {"id": label.id, "name": label.name}

        self.call(job, on_done)

    def rename_label(self, label_id: str, new_name: str, on_done: Callback = None) -> None:
        def job() -> dict:
            label = self.keep.getLabel(label_id)
            if label is None:
                raise ServiceError("Etiket bulunamadı.")
            label.name = new_name.strip()
            self._after_edit(delay=0.4)
            return {"id": label.id, "name": label.name}

        self.call(job, on_done)

    def delete_label(self, label_id: str, on_done: Callback = None) -> None:
        def job() -> None:
            self.keep.deleteLabel(label_id)
            self._after_edit(delay=0.4)

        self.call(job, on_done)

    def convert(self, note_id: str, target: str, on_done: Callback = None) -> None:
        """Convert between a text note and a checklist, preserving content."""

        def job() -> dict:
            node = self._node(note_id)
            title = node.title or ""
            color = node.color.value if node.color else "DEFAULT"
            pinned = bool(node.pinned)
            labels = [label.name for label in node.labels.all()]

            if target == "list" and not isinstance(node, KeepList):
                items = [(line, False) for line in (node.text or "").splitlines() if line.strip()]
                new_node = self.keep.createList(title, items)
            elif target == "note" and isinstance(node, KeepList):
                text = "\n".join(
                    ("[x] " if item.checked else "") + item.text for item in node.items
                )
                new_node = self.keep.createNote(title, text)
            else:
                return self._snapshot(node) or {}

            new_node.color = ColorValue(color)
            new_node.pinned = pinned
            for name in labels:
                label = self.keep.findLabel(name, create=True)
                if label:
                    new_node.labels.add(label)
            node.delete()
            self._after_edit(delay=0.3)
            return self._snapshot(new_node) or {}

        self.call(job, on_done)
