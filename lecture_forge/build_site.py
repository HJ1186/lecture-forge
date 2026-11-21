"""Stage 4 - build the static site (lecture page + ask page).

Input layout (the "lecture source" folder)::

    lecture.md        the notes, plain Markdown, images as img/xxx.png
    meta.json         {"title": "...", "subtitle": "...", "lang": "zh"}
    qa-bank.json      [{"id","pin","q","a":[...],"tags":[...]}, ...]
    img/              figures used by lecture.md

Output::

    site/index.html   lecture + dock (inline CSS/JS, no CDN, works offline)
    site/ask.html     standalone "paste a paragraph, ask a question" page
    site/img/...      copied figures

A bank entry with ``"pin": "三、"`` becomes an inline note right after the
``## 三、`` heading - that is the whole point of the bank: the questions live
next to the text that provokes them.
"""

from __future__ import annotations

import json
import os
import re
import shutil

from .util import die, ensure_dir, info, warn

TPL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _read(p: str, default: str = "") -> str:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def _md_to_html(text: str) -> str:
    try:
        import markdown
    except Exception:
        die("this stage needs `markdown`:\n  python -m pip install -U markdown")
        raise
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "nl2br"])


def _note_html(entry: dict, open_: bool = False) -> str:
    items = "".join("<li>%s</li>" % _esc_points(x) for x in entry.get("a") or [])
    return (
        '<aside class="nq" data-qid="%s"><details%s><summary>%s</summary><ul>%s</ul></details></aside>'
        % (_esc_attr(entry.get("id", "")), " open" if open_ else "",
           _esc_text(entry.get("q", "")), items)
    )


def _esc_text(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return _esc_text(s).replace('"', "&quot;")


def _esc_points(s: str) -> str:
    """Bank points are plain text; light-touch emphasis for **bold** / `code`."""
    t = _esc_text(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def _strip_title(md: str, meta: dict) -> str:
    """The template owns the <h1>. Drop the markdown's own leading '# title'
    so the page never shows the heading twice (and fill the title from it)."""
    lines = md.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and re.match(r"^#\s+\S", lines[i]):
        title = lines[i].lstrip("# ").strip()
        meta.setdefault("title", title)
        md = "\n".join(lines[:i] + lines[i + 1:])
    return md


def _inject_notes(html: str, bank: list) -> str:
    pins = {}
    for e in bank:
        pins.setdefault(e.get("pin") or "", []).append(e)
    if not pins:
        return html

    def repl(m):
        h2 = m.group(1)
        text = re.sub(r"<[^>]+>", "", h2).strip()
        for pin, entries in pins.items():
            if pin and text.startswith(pin):
                return h2 + "".join(_note_html(e, bool(e.get("open"))) for e in entries)
        return h2

    return re.sub(r"(<h2[^>]*>.*?</h2>)", repl, html, flags=re.S)


def build(src: str, outdir: str, cfg: dict | None = None, embed: bool = False) -> str:
    if not os.path.isdir(src):
        die("lecture folder not found: %s" % src)
    md_path = os.path.join(src, "lecture.md")
    if not os.path.isfile(md_path):
        die("missing lecture.md in %s" % src)
    cfg = cfg or {}
    meta = {}
    if os.path.isfile(os.path.join(src, "meta.json")):
        meta = json.loads(_read(os.path.join(src, "meta.json"), "{}") or "{}")
    bank = []
    bpath = os.path.join(src, "qa-bank.json")
    if os.path.isfile(bpath):
        bank = json.loads(_read(bpath, "[]") or "[]")
        if isinstance(bank, dict):
            bank = bank.get("entries", [])
    title = meta.get("title") or "讲义"
    lang = meta.get("lang") or "zh"
    subtitle = meta.get("subtitle") or ""
    api = meta.get("api", "")

    body = _inject_notes(_md_to_html(_strip_title(_read(md_path), meta)), bank)
    ensure_dir(outdir)

    if embed:
        body = _embed_images(body, src)

    css = _read(os.path.join(TPL, "site.css"))
    js = _read(os.path.join(TPL, "app.js"))
    conf = {"title": title, "api": api, "lang": lang}

    page = _read(os.path.join(TPL, "lecture.tpl.html"))
    page = (page.replace("__CSS__", css).replace("__TITLE__", _esc_text(title))
            .replace("__LANG__", lang).replace("__JS__", js)
            .replace("__BANK__", json.dumps(bank, ensure_ascii=False))
            .replace("__CONFIG__", json.dumps(conf, ensure_ascii=False)))
    sub = ""
    if subtitle:
        sub = "<blockquote><p>%s</p></blockquote>" % _esc_text(subtitle).replace("\n", "<br>")
    page = page.replace("__SUBTITLE__", sub).replace("__BODY__", body)
    out_index = os.path.join(outdir, "index.html")
    with open(out_index, "w", encoding="utf-8") as f:
        f.write(page)

    ask = _read(os.path.join(TPL, "ask.tpl.html"))
    ask = (ask.replace("__CSS__", css).replace("__TITLE__", _esc_text(title))
           .replace("__LANG__", lang).replace("__JS__", js)
           .replace("__BANK__", json.dumps(bank, ensure_ascii=False))
           .replace("__CONFIG__", json.dumps(conf, ensure_ascii=False)))
    with open(os.path.join(outdir, "ask.html"), "w", encoding="utf-8") as f:
        f.write(ask)

    # figures + the bank (the server reads site/qa-bank.json when no key is set)
    if os.path.isfile(bpath):
        shutil.copy2(bpath, os.path.join(outdir, "qa-bank.json"))
    src_img = os.path.join(src, "img")
    dst_img = os.path.join(outdir, "img")
    n_img = 0
    if os.path.isdir(src_img):
        ensure_dir(dst_img)
        for name in os.listdir(src_img):
            s = os.path.join(src_img, name)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(dst_img, name))
                n_img += 1

    info("built %s  (notes pinned: %d, bank: %d, images: %d, embed: %s)"
         % (outdir, sum(1 for e in bank if e.get("pin")), len(bank), n_img, embed))
    if not bank:
        warn("qa-bank.json is empty: the ask box will still work with a model, but has nothing offline")
    return out_index


def _embed_images(body: str, src: str) -> str:
    def repl(m):
        rid = m.group(1)
        path = os.path.join(src, rid)
        if not os.path.isfile(path):
            return m.group(0)
        import base64

        ext = os.path.splitext(rid)[1].lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}.get(ext, "image/png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return m.group(0).replace('src="%s"' % rid, 'src="data:%s;base64,%s"' % (mime, b64))

    return re.sub(r'<img[^>]*?src="([^"]+)"', repl, body)
