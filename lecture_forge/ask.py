"""One-shot question against the configured model, or the offline question bank.

The browser dock asks the running server; this module is the same thing without
a browser, which is what an agent or a terminal user needs:

    python -m lecture_forge ask "为什么互电阻是负的？" --context "把讲义那一段贴进来"

No history is kept: one question in, one answer out. With no `model.api_key`
configured it falls back to the lecture's `qa-bank.json` instead of inventing an
answer.

@module lecture_forge.ask
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

from .serve import FALLBACK_SYSTEM, _bank_search, _norm, _system_prompt
from .util import load_config

__all__ = ["ask"]


def _read_bank(path: str | None) -> list:
    """Load a qa-bank.json (a bare list or {"entries": [...]}), or [] if unreadable."""
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        entries = data.get("entries")
        return entries if isinstance(entries, list) else []
    return data if isinstance(data, list) else []


def _call_model(model: dict, question: str, context: str, timeout: float) -> str:
    """POST one chat completion and return the answer text."""
    base = (model.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    user = ""
    if context:
        user += "【我正在读的材料】\n" + context + "\n\n"
    user += "【我的问题】\n" + question
    body = {
        "model": model.get("model") or "gpt-4o-mini",
        "temperature": float(model.get("temperature", 0.3)),
        "max_tokens": int(model.get("max_tokens", 900)),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + str(model["api_key"]),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    choices = data.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content", "").strip()


def ask(
    question: str,
    config_path: str | None = None,
    context: str = "",
    bank_path: str | None = None,
    timeout: float = 120,
) -> dict:
    """Answer one question.

    Parameters
    ----------
    question:
        The single question to answer.
    config_path:
        Path to config.json; ``None`` looks in the current directory.
    context:
        Material to answer from (a passage, a problem statement, notes).
    bank_path:
        qa-bank.json used when no model key is configured.
    timeout:
        Seconds to wait for the model.

    Returns
    -------
    dict
        ``{"ok", "mode", "answer", ...}``; ``mode`` is ``"model"`` or ``"bank"``.
    """
    question = (question or "").strip()
    if not question:
        return {"ok": False, "mode": "bank", "answer": "", "error": "question is empty"}

    config = load_config(config_path)
    model = config.get("model") or {}
    if model.get("api_key"):
        try:
            answer = _call_model(model, question, context, timeout)
        except Exception as exc:  # noqa: BLE001 - the caller wants the reason, not a traceback
            return {
                "ok": False,
                "mode": "model",
                "answer": "",
                "error": "模型调用失败：%s" % exc,
            }
        return {
            "ok": bool(answer),
            "mode": "model",
            "answer": answer,
            "model": model.get("model"),
        }

    bank = _read_bank(bank_path)
    hits = _bank_search(bank, question)
    if hits:
        best = hits[0]
        points = best.get("a") or []
        return {
            "ok": True,
            "mode": "bank",
            "answer": "\n".join("- " + str(p) for p in points),
            "matched": best.get("q") or "",
            "hits": len(hits),
            "note": "离线题库命中（%d 条）；在 config.json 填 model.api_key 后可以问任意问题" % len(hits),
        }
    return {
        "ok": False,
        "mode": "bank",
        "answer": "",
        "error": "题库未命中；在 config.json 填 model.api_key 后可以问任意问题",
        "note": "" if bank else "没有找到 qa-bank.json（用 --bank 指定，或先 build 一次）",
    }


def main(argv: list[str] | None = None) -> int:
    """CLI wrapper used by ``python -m lecture_forge ask``."""
    import argparse

    parser = argparse.ArgumentParser(prog="lecture_forge ask", description="Ask one question about a lecture.")
    parser.add_argument("question")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--context", default="")
    parser.add_argument("--context-file", default=None, help="read the material from a file instead")
    parser.add_argument("--bank", default=None, help="qa-bank.json for the offline fallback")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--json", action="store_true", help="print the raw result object")
    args = parser.parse_args(argv)

    context = args.context
    if args.context_file:
        try:
            with open(args.context_file, "r", encoding="utf-8") as f:
                context = f.read()
        except OSError as exc:
            print("cannot read --context-file: %s" % exc, file=sys.stderr)
            return 2

    result = ask(args.question, args.config, context, args.bank, args.timeout)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if result.get("answer"):
        print(result["answer"])
        if result.get("note"):
            print("\n（%s）" % result["note"], file=sys.stderr)
        return 0
    print(result.get("error") or "没有答案", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
