"""Shared helpers: config loading, paths, console output."""

from __future__ import annotations

import json
import os
import sys

# Anything user-specific (API keys, machine paths) belongs in config.json,
# which is git-ignored.  config.example.json documents every field.
DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8765,
    "site_dir": "site",
    "model": {
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 900,
    },
    "asr": {
        "model": "large-v3",
        "device": "auto",
        "compute_type": "auto",
        "language": "zh",
        "beam_size": 5,
        "initial_prompt": "",
        "download_root": "",
        "local_files_only": False,
    },
}


def deep_update(base: dict, extra: dict) -> dict:
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | None = None) -> dict:
    """Load config.json (if present) merged over the defaults."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    candidates = [path] if path else ["config.json", os.path.join(os.path.dirname(__file__), "..", "config.json")]
    for c in candidates:
        if c and os.path.isfile(c):
            with open(c, "r", encoding="utf-8") as f:
                deep_update(cfg, json.load(f))
            break
    return cfg


def info(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print("warning: " + msg, file=sys.stderr, flush=True)


def die(msg: str, code: int = 1):
    print("error: " + msg, file=sys.stderr, flush=True)
    raise SystemExit(code)


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%d %s" % (round(n), unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def mmss(seconds: float) -> str:
    """Seconds -> mm:ss (or h:mm:ss past an hour)."""
    seconds = int(max(0, round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)
