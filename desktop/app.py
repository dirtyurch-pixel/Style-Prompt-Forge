"""Style Prompt Forge - desktop app for building Suno v6 prompts.

Runs a small local server and opens it in its own Microsoft Edge app window (same idea as Lyric Studio).
Everything you save lives in the "data" folder next to this file, and is copied to OneDrive when it's there.
The Ask Claude buttons use your Claude API key (the one Lyric Studio already has is used automatically).
"""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import anthropic

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STORE_FILE = DATA_DIR / "store.json"        # the Forge's saved songs, recipes, chords, singers, log
SETTINGS_FILE = DATA_DIR / "settings.json"  # model choice and the (Windows-locked) API key
USAGE_FILE = DATA_DIR / "usage.json"
LOCAL_BACKUPS = DATA_DIR / "backups"
INSTANCE_FILE = DATA_DIR / "instance.json"
PAGE_FILE = APP_DIR / "Style Prompt Forge.html"
SHIM_FILE = APP_DIR / "desktop.js"
FILES = {"/forge.ico": "image/x-icon", "/icon-192.png": "image/png"}

# USD per million tokens: input, output
MODELS = {
    "claude-opus-5-5": {"name": "Opus 5.5 (best)", "in": 4.00, "out": 20.00, "fallbacks": True},
    "claude-sonnet-5-5": {"name": "Sonnet 5.5 (half price)", "in": 2.00, "out": 10.00, "fallbacks": True},
    "claude-haiku-5-5": {"name": "Haiku 5.5 (cheapest)", "in": 0.10, "out": 0.50, "fallbacks": False},
}
DEFAULT_MODEL = "claude-opus-5-5"
MARK = "\x1e"  # separates the streamed answer from the info sent at the end

DATA_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()
_backup = {"dirty": False, "last": None, "error": None, "folder": None}


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def settings():
    s = load_json(SETTINGS_FILE, {})
    if s.get("model") not in MODELS:
        s["model"] = DEFAULT_MODEL
    s.setdefault("cloud_backup", True)
    return s


# ---------- API key: locked with Windows' own encryption (DPAPI), like Lyric Studio ----------
def _dpapi(data, encrypt):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    src, out = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), BLOB()
    if encrypt:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(src), "Style Prompt Forge", None, None, None, 0x1, ctypes.byref(out))
    else:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("Windows couldn't " + ("lock" if encrypt else "unlock") + " the API key")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def lock_key(key):
    return base64.b64encode(_dpapi(key.encode("utf-8"), True)).decode("ascii")


def unlock_key(blob):
    return _dpapi(base64.b64decode(blob), False).decode("utf-8")


def lyric_studio_settings():
    """Lyric Studio's settings file, if it's on this PC (its key can be shared)."""
    homes = [Path.home() / "Desktop"]
    for env in ("OneDrive", "OneDriveConsumer"):
        if os.environ.get(env):
            homes.append(Path(os.environ[env]) / "Desktop")
    for h in homes:
        p = h / "Lyric Studio" / "data" / "settings.json"
        if p.exists():
            return p
    return None


def get_api_key():
    """Returns (key, where it came from)."""
    s = settings()
    if s.get("api_key_locked"):
        try:
            return unlock_key(s["api_key_locked"]), "saved in the Forge"
        except Exception:
            pass
    if s.get("api_key"):
        return s["api_key"], "saved in the Forge"
    if not s.get("ignore_lyric_studio"):
        p = lyric_studio_settings()
        if p:
            ls = load_json(p, {})
            try:
                if ls.get("api_key_locked"):
                    return unlock_key(ls["api_key_locked"]), "shared from Lyric Studio"
            except Exception:
                pass
            if ls.get("api_key"):
                return ls["api_key"], "shared from Lyric Studio"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"], "from Windows settings"
    return "", ""


def month_usd():
    month = time.strftime("%Y-%m")
    return round(sum(r["usd"] for r in load_json(USAGE_FILE, []) if r.get("t", "").startswith(month)), 4)


def record_usage(model, usage):
    p = MODELS[model]
    usd = (usage.input_tokens * p["in"] + usage.output_tokens * p["out"]) / 1_000_000
    with _lock:
        rows = load_json(USAGE_FILE, [])
        rows.append({"t": time.strftime("%Y-%m-%d %H:%M"), "model": model, "usd": round(usd, 5)})
        save_json(USAGE_FILE, rows[-3000:])
    return usd


# ---------- backups: a dated copy each day here, plus a copy in OneDrive ----------
def cloud_folder():
    for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        p = os.environ.get(env)
        if p and Path(p).is_dir():
            return Path(p)
    return None


def backup_now():
    if not STORE_FILE.exists():
        return
    try:
        LOCAL_BACKUPS.mkdir(exist_ok=True)
        shutil.copy2(STORE_FILE, LOCAL_BACKUPS / f"forge {time.strftime('%Y-%m-%d')}.json")
        for old in sorted(LOCAL_BACKUPS.glob("forge *.json"))[:-14]:  # keep two weeks
            old.unlink()
        cloud = cloud_folder()
        if cloud and settings().get("cloud_backup"):
            target = cloud / "Style Prompt Forge Backup"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(STORE_FILE, target / "store.json")
            _backup["folder"] = str(target)
        _backup.update(dirty=False, last=time.strftime("%Y-%m-%d %H:%M"), error=None)
    except OSError as e:
        _backup["error"] = str(e)


def backup_loop():
    while True:
        if _backup["dirty"]:
            backup_now()
        time.sleep(30)


def page_html():
    html = PAGE_FILE.read_text(encoding="utf-8")
    store = load_json(STORE_FILE, {})
    seed = json.dumps(store, ensure_ascii=False).replace("</", "<\\/")
    shim = SHIM_FILE.read_text(encoding="utf-8").replace("__SEED__", seed)
    return html.replace("<head>", "<head>\n<script>\n" + shim + "\n</script>", 1).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # lets the answer stream until the connection closes

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def do_GET(self):
        if not self._local():
            return self._send(403, {"error": "This PC only"})
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, page_html(), "text/html; charset=utf-8")
        elif path in FILES and (APP_DIR / path.lstrip("/")).exists():
            self._send(200, (APP_DIR / path.lstrip("/")).read_bytes(), FILES[path])
        elif path == "/api/settings":
            key, src = get_api_key()
            s = settings()
            self._send(200, {"has_key": bool(key), "key_hint": ("…" + key[-4:]) if key else "", "key_from": src,
                             "lyric_studio": bool(lyric_studio_settings()), "model": s["model"],
                             "models": [[k, v["name"]] for k, v in MODELS.items()], "month_usd": month_usd(),
                             "cloud": str(cloud_folder() or ""), "cloud_backup": s["cloud_backup"],
                             "last_backup": _backup["last"], "backup_error": _backup["error"],
                             "data_dir": str(DATA_DIR)})
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        if not self._local():
            return self._send(403, {"error": "This PC only"})
        path = urlparse(self.path).path
        if path == "/api/store":
            d = self._body()
            if isinstance(d, dict):
                with _lock:
                    save_json(STORE_FILE, {k: v for k, v in d.items() if isinstance(k, str) and k.startswith("forge")})
                    _backup["dirty"] = True
            self._send(200, {"ok": True})
        elif path == "/api/settings":
            d = self._body()
            with _lock:
                s = load_json(SETTINGS_FILE, {})
                if d.get("model") in MODELS:
                    s["model"] = d["model"]
                if "cloud_backup" in d:
                    s["cloud_backup"] = bool(d["cloud_backup"])
                if d.get("clear_key"):
                    s.pop("api_key_locked", None)
                    s.pop("api_key", None)
                    s["ignore_lyric_studio"] = True
                if d.get("use_lyric_studio"):
                    s.pop("api_key_locked", None)
                    s.pop("api_key", None)
                    s.pop("ignore_lyric_studio", None)
                key = (d.get("key") or "").strip()
                if key:
                    try:
                        blob = lock_key(key)
                        if unlock_key(blob) != key:
                            raise OSError
                        s["api_key_locked"] = blob
                        s.pop("api_key", None)
                    except Exception:
                        s["api_key"] = key
                save_json(SETTINGS_FILE, s)
            self._send(200, {"ok": True})
        elif path == "/api/open-data":
            try:
                os.startfile(str(DATA_DIR))  # Windows: opens the folder in File Explorer
            except Exception:
                pass
            self._send(200, {"ok": True})
        elif path == "/api/backup-now":
            backup_now()
            self._send(200, {"ok": not _backup["error"], "last": _backup["last"], "error": _backup["error"]})
        elif path == "/api/sample":
            self.sample(self._body())
        else:
            self._send(404, {"error": "Not found"})

    def sample(self, d):
        key, _ = get_api_key()
        if not key:
            return self._send(400, {"error": "Add your Claude API key first: Tools › Claude & this PC."})
        prompt = d.get("prompt")
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
        if not messages:
            return self._send(400, {"error": "Nothing to send"})
        model = settings()["model"]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(text):
            self.wfile.write(text.encode("utf-8"))
            self.wfile.flush()

        params = dict(model=model, max_tokens=16000, messages=messages,
                      thinking={"type": "adaptive"}, output_config={"effort": "medium"})
        if MODELS[model]["fallbacks"]:
            params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        client = anthropic.Anthropic(api_key=key)
        try:
            for attempt in range(3):
                try:
                    with client.beta.messages.stream(**params) as stream:
                        for text in stream.text_stream:
                            emit(text)
                        final = stream.get_final_message()
                    break
                except anthropic.BadRequestError as e:
                    msg = str(e).lower()
                    if attempt < 2 and "fallback" in msg and "fallbacks" in params:
                        params.pop("fallbacks"); params.pop("betas")
                        continue
                    if attempt < 2 and ("output_config" in msg or "effort" in msg or "thinking" in msg):
                        params.pop("output_config", None); params.pop("thinking", None)
                        continue
                    raise
            note = ""
            if final.stop_reason == "refusal":
                note = "Claude declined this request. Try rewording it."
            elif final.stop_reason == "max_tokens":
                note = "Stopped: the answer got too long."
            usd = record_usage(model, final.usage)
            emit(MARK + json.dumps({"usd": usd, "month_usd": month_usd(), "note": note}))
        except anthropic.AuthenticationError:
            emit(MARK + json.dumps({"error": "Claude didn't accept the API key. Check it in Tools › Claude & this PC."}))
        except anthropic.RateLimitError:
            emit(MARK + json.dumps({"error": "Too many requests or out of credit. Wait a moment, or add credit in the Claude Console."}))
        except anthropic.APIStatusError as e:
            emit(MARK + json.dumps({"error": f"Claude error {e.status_code}: {getattr(e, 'message', e)}"}))
        except anthropic.APIConnectionError:
            emit(MARK + json.dumps({"error": "Couldn't reach Claude. Check your internet connection."}))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Stop was pressed, or the window was closed


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def open_window(url, wait):
    edge = find_edge()
    if edge:
        proc = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={DATA_DIR / 'window'}",
                                 "--window-size=1200,900", "--no-first-run", "--no-default-browser-check"])
        if wait:
            proc.wait()
        return
    webbrowser.open(url)
    if wait:
        while True:
            time.sleep(3600)


def running_instance():
    port = load_json(INSTANCE_FILE, {}).get("port")
    if not port:
        return None
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/settings", timeout=1.5) as r:
            return port if r.status == 200 else None
    except Exception:
        return None


def main():
    no_window = "--no-window" in sys.argv
    if not no_window:
        old = running_instance()
        if old:  # already open: just show another window
            open_window(f"http://127.0.0.1:{old}/", wait=False)
            return
    port = int(os.environ.get("FORGE_PORT") or free_port())
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    if no_window:
        print("Serving on", url, flush=True)
        while True:
            time.sleep(3600)
    save_json(INSTANCE_FILE, {"port": port, "pid": os.getpid()})
    try:
        open_window(url, wait=True)  # app window closed -> quit
    finally:
        backup_now()
        try:
            if load_json(INSTANCE_FILE, {}).get("pid") == os.getpid():
                INSTANCE_FILE.unlink()
        except OSError:
            pass
        server.shutdown()


if __name__ == "__main__":
    main()
