import os
import time

import requests


def env(name, default=""):
    return os.getenv(name, default).strip()


def api_version():
    return env("META_API_VERSION", "v26.0")


def graph_url(path):
    return f"https://graph.facebook.com/{api_version()}/{path.lstrip('/')}"


def check(resp):
    """Meta API response ko JSON mein badlo; error ho to saaf message ke saath raise karo."""
    try:
        data = resp.json()
    except ValueError:
        if resp.ok:
            return {}
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if not resp.ok or (isinstance(data, dict) and "error" in data):
        err = data.get("error", {}) if isinstance(data, dict) else {}
        debug = data.get("debug_info") if isinstance(data, dict) else None
        if isinstance(err, dict) and err:
            msg = err.get("error_user_msg") or err.get("message") or resp.text[:300]
            code = err.get("code")
        elif isinstance(debug, dict):
            # rupload.facebook.com wale errors is format mein aate hain
            msg, code = f"{debug.get('type', 'Error')}: {debug.get('message', '')}", None
        else:
            msg, code = (str(err) if err else resp.text[:300]), None
        raise RuntimeError(f"{msg} (code {code})" if code else msg)
    return data


class ProgressFile:
    """File ko stream karta hai aur kitna bhej diya uska callback deta hai (0.0 - 1.0)."""

    def __init__(self, path, on_progress):
        self.f = open(path, "rb")
        self.size = os.path.getsize(path)
        self.sent = 0
        self.on_progress = on_progress
        self._last = 0.0

    def __len__(self):
        return self.size

    def read(self, n=-1):
        chunk = self.f.read(n if n and n > 0 else 1024 * 1024)
        self.sent += len(chunk)
        now = time.monotonic()
        if now - self._last > 0.5 or self.sent >= self.size:
            self._last = now
            self.on_progress(self.sent / self.size if self.size else 1.0)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.f.close()
