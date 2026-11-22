"""Stage 5 - a tiny local server for the ask box.

Why a server at all?  Because the model key must never sit inside the HTML
that you might share, and because ``fetch()`` from a ``file://`` page cannot
call an API directly.  So the page talks to ``127.0.0.1`` and this process
holds the key.

Endpoints::

    GET  /            the lecture page
    GET  /ask.html    the standalone ask page
    GET  /img/<name>  figures
    GET  /ping        {"ok":true,"mode":"model"|"bank","bank":N}
    POST /ask         {"q":"...","ctx":"..."} -> {"ok":true,"a":"...","src":"..."}

With an empty ``model.api_key`` the server still works: it answers from
``qa-bank.json`` (the same bank the page uses offline), and says so.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .util import die, load_config, warn

PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "qa-system.md")

FALLBACK_SYSTEM = """你是一位耐心的老师，正在回答学生关于一份讲义的提问。
回答必须按这个顺序写，用短句，不要客套：
1. 定义：这件事按定义是什么（一句）。
2. 对照：拿材料里的具体对象逐条对照。
3. 规则：由定义得到什么结论。
4. 算式/步骤：把数字或步骤代进去。
5. 一句话：最后用一句话让人记住。
只回答被问到的这一件事；材料里没有的信息不要编造，直接说不确定。"""


def _system_prompt() -> str:
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return FALLBACK_SYSTEM


# --- config, re-read when the file changes ----------------------------------
# Why: people start the server, then paste their api_key into config.json and
# wonder why the page still says "bank". Reading the config once at startup
# turns a five-second edit into a "you must restart" mystery. So the mtime is
# checked on every request and the file is reloaded when it moves.
_CONFIG_PATH: str = ""
_CFG: dict = {}
_CFG_MTIME: float = -1.0


def cfg() -> dict:
    """Current config, reloaded automatically after the file is edited."""
    global _CFG, _CFG_MTIME
    p = _CONFIG_PATH or "config.json"
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        mtime = 0.0
    if _CFG_MTIME < 0 or mtime != _CFG_MTIME:
        first = _CFG_MTIME < 0
        _CFG = load_config(_CONFIG_PATH or None)
        _CFG_MTIME = mtime
        if not first:
            print("  [config] config.json changed - reloaded, no restart needed")
    return _CFG


def _norm(s: str) -> str:
    return re.sub(r"[\s,.;:!?\"'`()\[\]{}<>，。；：！？“”‘’（）【】《》、·\-—…/\\]+", "", (s or "").lower())


def _bank_search(bank: list, q: str) -> list:
    nq = _norm(q)
    scored = []
    for e in bank:
        full = _norm((e.get("q") or "") + "".join(e.get("a") or []) + "".join(e.get("tags") or []))
        sc = 0
        if nq and nq in _norm(e.get("q") or ""):
            sc += 100
        if nq and len(nq) >= 2 and nq in full:
            sc += 40
        for t in e.get("tags") or []:
            nt = _norm(t)
            if nt and nq and nt in nq:
                sc += 45
        if len(nq) >= 2:
            sc += 2 * sum(1 for i in range(len(nq) - 1) if nq[i:i + 2] in full)
        if sc:
            scored.append((sc, e))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return []
    cut = max(24, scored[0][0] * 0.62)
    return [e for s, e in scored if s >= cut][:3]


class Handler(BaseHTTPRequestHandler):
    server_version = "lecture-forge/0.1"
    site: str = ""

    def log_message(self, fmt, *a):  # keep the console usable
        return

    # ---------- helpers ----------
    def _send(self, code: int, body: bytes, ctype: str = "application/octet-stream"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _file(self, rel: str):
        rel = rel.lstrip("/").replace("\\", "/") or "index.html"
        if rel in ("", "index.html"):
            rel = "index.html"
        if rel == "ask":
            rel = "ask.html"
        root = os.path.abspath(self.site)
        path = os.path.abspath(os.path.join(root, rel))
        if not path.startswith(root + os.sep) and path != root:
            return self._send(403, b"forbidden", "text/plain")
        if not os.path.isfile(path):
            return self._send(404, b"not found", "text/plain")
        mime = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
                ".webp": "image/webp", ".svg": "image/svg+xml"}.get(
                    os.path.splitext(path)[1].lower(), "application/octet-stream")
        with open(path, "rb") as f:
            self._send(200, f.read(), mime)

    # ---------- routes ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/ping":
            m = cfg().get("model") or {}
            bank = self._bank()
            return self._json({"ok": True, "mode": "model" if m.get("api_key") else "bank", "bank": len(bank)})
        return self._file(p)

    def do_POST(self):
        if self.path.split("?")[0] != "/ask":
            return self._json({"ok": False, "error": "unknown endpoint"}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8-sig", "ignore")
            payload = json.loads(text.lstrip("\ufeff") or "{}")
        except Exception as e:
            return self._json({"ok": False, "error": "bad request: %s" % e}, 400)
        q = (payload.get("q") or "").strip()
        ctx = (payload.get("ctx") or "").strip()
        if not q:
            return self._json({"ok": False, "error": "empty question"}, 400)
        m = cfg().get("model") or {}
        if not m.get("api_key"):
            hits = _bank_search(self._bank(), q)
            if not hits:
                return self._json({"ok": False, "error": "题库未命中；在 config.json 填 model.api_key 后可以问任意问题",
                                   "mode": "bank"})
            best = hits[0]
            return self._json({"ok": True, "mode": "bank", "q": best.get("q"), "a": "\n".join("- " + x for x in best.get("a") or []),
                               "src": "离线题库（%d 条命中）" % len(hits)})
        try:
            text = self._call_model(m, q, ctx)
        except Exception as e:
            return self._json({"ok": False, "error": "模型调用失败：%s" % e}, 502)
        return self._json({"ok": True, "mode": "model", "q": q, "a": text,
                           "src": "%s · 只答这一问" % m.get("model", "model")})

    # ---------- model ----------
    def _call_model(self, m: dict, q: str, ctx: str) -> str:
        base = (m.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        url = base + "/chat/completions"
        user = ""
        if ctx:
            user += "【我正在读的材料】\n" + ctx + "\n\n"
        user += "【我的问题】\n" + q
        body = {
            "model": m.get("model") or "gpt-4o-mini",
            "temperature": float(m.get("temperature", 0.3)),
            "max_tokens": int(m.get("max_tokens", 900)),
            "messages": [{"role": "system", "content": _system_prompt()},
                         {"role": "user", "content": user}],
        }
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + m["api_key"]})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()

    def _bank(self) -> list:
        for name in ("qa-bank.json", os.path.join("lecture", "qa-bank.json")):
            p = os.path.join(self.site, name)
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        b = json.load(f)
                    return b.get("entries", []) if isinstance(b, dict) else b
                except Exception:
                    return []
        return []


def serve(config_path: str | None = None) -> None:
    global _CONFIG_PATH
    _CONFIG_PATH = config_path or ""
    conf = cfg()
    site = conf.get("site_dir") or "site"
    if not os.path.isdir(site):
        die("site folder not found: %s\n  build it first: python -m lecture_forge build <lecture-folder> -o site" % site)
    Handler.site = site
    host, port = conf.get("host", "127.0.0.1"), int(conf.get("port", 8765))
    httpd = ThreadingHTTPServer((host, port), Handler)
    m = conf.get("model") or {}
    print("lecture-forge serving %s" % os.path.abspath(site))
    print("  page : http://%s:%d/" % (host, port))
    print("  ask  : http://%s:%d/ask.html" % (host, port))
    print("  mode : %s" % ("model -> " + str(m.get("model")) if m.get("api_key") else
                           "bank only (fill model.api_key in config.json to ask anything)"))
    print("  note : config.json is re-read on every request - edit it, then refresh the page")
    print("  stop : Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
