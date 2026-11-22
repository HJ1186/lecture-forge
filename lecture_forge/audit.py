"""Stage 6 - the pre-publish audit.

Publishing leaks in a very repeatable way, so the checks are fixed rather than
ad hoc.  Run it before every push::

    python -m lecture_forge audit .

Six groups, in the order you should care about them:

1. secrets      - keys, tokens, private keys, .env, credential files
2. privacy      - phone numbers, ID cards, real email addresses
3. abs paths    - C:\\Users\\..., /home/..., file:///... in tracked files
4. temp files   - editor leftovers, logs, caches, backups
5. junk         - build output, node_modules, virtualenvs, big binaries
6. not public   - internal / confidentiality markers, copyrighted source media  (audit:ignore)

Exit code is 0 only when nothing blocking was found.  Secrets and personal
data are printed **masked** - the audit never echoes a live credential.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "dist", "build", ".venv", "venv",
             "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"}

TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yml", ".yaml", ".html", ".css",
            ".toml", ".cfg", ".ini", ".sh", ".ps1", ".bat", ".cmd", ".c", ".h", ".java",
            ".svg", ".gitignore", ".gitattributes", ""}

SECRET_RULES = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("openai/llm key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("github pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("bearer literal", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-\._~\+/]{24,}")),
    ("assigned secret", re.compile(
        r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|pwd)\b"
        r"\s*[:=]\s*[\"']?([A-Za-z0-9\-\._~\+/]{12,})[\"']?")),
]

PRIVACY_RULES = [
    ("cn mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("cn id card", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
]

SAFE_EMAIL_DOMAINS = ("users.noreply.github.com", "example.com", "example.org",
                      "example.net", "localhost", "test.local", "@2x.png")

ABS_PATH_RULES = [
    ("windows user path", re.compile(r"\b[A-Za-z]:\\(?:Users|Documents and Settings)\\[^\\\s\"']+", re.I)),
    ("windows abs path", re.compile(r"(?<![\w])[A-Za-z]:\\[^\s\"'<>|]{3,}")),
    ("posix home path", re.compile(r"(?<![\w])/(?:Users|home)/[A-Za-z0-9._\-]+/")),
    ("file url", re.compile(r"file:///", re.I)),
    ("unc path", re.compile(r"\\\\[A-Za-z0-9._\-]+\\[A-Za-z0-9$._\-]+")),
]

TEMP_PATTERNS = [r"\.tmp$", r"\.temp$", r"\.bak$", r"\.old$", r"\.orig$", r"\.rej$", r"~$",
                 r"^~\$", r"\.log$", r"\.swp$", r"\.swo$", r"^\.DS_Store$", r"^Thumbs\.db$",
                 r"\.pyc$", r"^_t_", r"^_chk", r"^_shot", r"^_dump", r"\.dump$", r"\.cache$",
                 r"^nul$", r"\.ipynb_checkpoints$"]

JUNK_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", ".idea", ".vscode", ".ipynb_checkpoints"}

SOURCE_MEDIA = {".mp4", ".mkv", ".avi", ".mov", ".m4a", ".mp3", ".wav", ".flac",
                ".pdf", ".epub", ".docx", ".pptx", ".xlsx"}

NOT_PUBLIC_RULES = [
    ("internal marker", re.compile(r"(?i)(仅供内部|内部资料|机密|绝密|不可外传|禁止外传|confidential|do not distribute|internal only)")),
]

MAX_BIN_BYTES = 5 * 1024 * 1024


class Finding:
    def __init__(self, group: str, level: str, where: str, what: str, detail: str = ""):
        self.group, self.level, self.where, self.what, self.detail = group, level, where, what, detail

    def as_dict(self):
        return {"group": self.group, "level": self.level, "file": self.where,
                "issue": self.what, "detail": self.detail}


def _mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return "*" * len(s)
    return s[:4] + "*" * (len(s) - 8) + s[-4:]


def _tracked_files(root: str) -> list[str]:
    """Prefer git's view (that is what would actually be published)."""
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True)
        files = [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]
        if files:
            untracked = subprocess.run(["git", "-C", root, "ls-files", "-o", "--exclude-standard", "-z"],
                                       capture_output=True, text=True, encoding="utf-8", errors="replace")
            files += [p for p in (untracked.stdout or "").split("\0") if p]
            return sorted(set(files))
    except Exception:
        pass
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            out.append(os.path.relpath(os.path.join(base, n), root).replace("\\", "/"))
    return sorted(out)


def _is_placeholder(line: str, m: re.Match) -> bool:
    """C:\\path\\to\\x, /home/<user>/, \\\\server\\share are documentation, not leaks."""
    hit = m.group(0)
    if any(tok in hit for tok in ("...", "<", ">", "path\\to", "path/to", "your", "example")):
        return True
    window = line[max(0, m.start() - 24): m.end() + 24]
    return any(tok in window for tok in ("...", "<user", "<name", "audit:ignore"))


def _skip_line(rel: str, line: str) -> bool:
    """Lines that must not be reported: the escape hatch, and the rule definitions."""
    if "audit:ignore" in line:
        return True
    return "re.compile" in line and "audit" in rel.replace("\\", "/")


def _scan_text(rel: str, path: str, findings: list[Finding]) -> None:
    ext = os.path.splitext(rel)[1].lower()
    if ext not in TEXT_EXT:
        return
    try:
        if os.path.getsize(path) > 3 * 1024 * 1024:
            return
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for i, line in enumerate(lines, 1):
        if _skip_line(rel, line):
            continue  # escape hatch / the rule definitions themselves
        for name, rx in SECRET_RULES:
            m = rx.search(line)
            if m:
                token = m.group(m.lastindex or 0) if m.lastindex else m.group(0)
                findings.append(Finding("1 secrets", "FAIL", "%s:%d" % (rel, i), name, _mask(token)))
        for name, rx in PRIVACY_RULES:
            m = rx.search(line)
            if not m:
                continue
            hit = m.group(0)
            if name == "email" and any(d in hit.lower() for d in SAFE_EMAIL_DOMAINS):
                continue
            if name == "email" and re.search(r"@[0-9.]+x\.[a-z]+$", hit):
                continue
            findings.append(Finding("2 privacy", "FAIL", "%s:%d" % (rel, i), name, _mask(hit)))
        for name, rx in ABS_PATH_RULES:
            m = rx.search(line)
            if m and not _is_placeholder(line, m):
                findings.append(Finding("3 abs paths", "FAIL", "%s:%d" % (rel, i), name, m.group(0)))
        for name, rx in NOT_PUBLIC_RULES:
            m = rx.search(line)
            if m:
                findings.append(Finding("6 not public", "WARN", "%s:%d" % (rel, i), name, m.group(0)))


def _scan_path(rel: str, path: str, findings: list[Finding]) -> None:
    base = os.path.basename(rel)
    low = rel.lower()
    if os.path.islink(path):
        findings.append(Finding("4 temp files", "WARN", rel, "symlink", "check it points to something public"))
    for pat in TEMP_PATTERNS:
        if re.search(pat, base, re.I):
            findings.append(Finding("4 temp files", "FAIL", rel, "temp/backup file", "delete it or gitignore it"))
            break
    if any(low.startswith(d + "/") for d in JUNK_DIRS) or "/" + "/".join([]) == "":
        pass
    if any(("/%s/" % d) in ("/" + low) for d in JUNK_DIRS):
        findings.append(Finding("5 junk", "FAIL", rel, "build/vendor folder", "must not be committed"))
    ext = os.path.splitext(base)[1].lower()
    if ext in SOURCE_MEDIA:
        findings.append(Finding("6 not public", "WARN", rel, "source media",
                                "only ship it if you have the right to redistribute"))
    try:
        size = os.path.getsize(path)
        if size > MAX_BIN_BYTES:
            findings.append(Finding("5 junk", "WARN", rel, ".big file",
                                    "%.1f MB - git handles it badly" % (size / 1048576.0)))
    except OSError:
        pass
    if base in (".env", "credentials.json", "id_rsa", "id_ed25519", ".npmrc", ".pypirc"):
        findings.append(Finding("1 secrets", "FAIL", rel, "credential file", "remove and rotate"))


def _scan_history(root: str, findings: list[Finding], limit_per_rule: int = 20) -> tuple[int, int]:
    """Scan every revision, not just the current tree.

    Deleting a line in a new commit does NOT remove it from the repo: the blob
    stays reachable through history and cloning still downloads it. This walks
    `git log -p --all` and tests only the ADDED lines, so a key that was pasted
    once and deleted still shows up (and must be rotated + history rewritten).

    Returns (commits_seen, lines_scanned).
    """
    try:
        out = subprocess.run(["git", "-C", root, "log", "--all", "--no-merges", "-p", "-U0",
                              "--format=@@@%H"], capture_output=True)
        if out.returncode != 0:
            return (0, 0)
        text = out.stdout.decode("utf-8", "replace")
    except Exception:
        return (0, 0)

    sha, rel, commits, lines = "", "", set(), 0
    seen: dict[str, int] = {}
    for raw in text.splitlines():
        if raw.startswith("@@@"):
            sha = raw[3:].strip()
            commits.add(sha)
            continue
        if raw.startswith("+++ "):
            p = raw[4:].strip()
            rel = p[2:] if p.startswith("b/") else p
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        line = raw[1:]
        lines += 1
        if _skip_line(rel, line):
            continue
        for name, rx in SECRET_RULES:
            m = rx.search(line)
            if not m:
                continue
            if _is_placeholder(line, m):
                continue
            key = "1 secrets|" + name
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= limit_per_rule:
                token = m.group(m.lastindex or 0) if m.lastindex else m.group(0)
                findings.append(Finding("1 secrets", "FAIL", "%s:%s" % (sha[:7], rel),
                                        name + " (in history)", _mask(token)))
        for name, rx in PRIVACY_RULES:
            m = rx.search(line)
            if not m:
                continue
            hit = m.group(0)
            if name == "email" and any(d in hit.lower() for d in SAFE_EMAIL_DOMAINS):
                continue
            key = "2 privacy|" + name
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= limit_per_rule:
                findings.append(Finding("2 privacy", "FAIL", "%s:%s" % (sha[:7], rel),
                                        name + " (in history)", _mask(hit)))
        for name, rx in ABS_PATH_RULES:
            m = rx.search(line)
            if not m or _is_placeholder(line, m):
                continue
            key = "3 abs paths|" + name
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= limit_per_rule:
                findings.append(Finding("3 abs paths", "FAIL", "%s:%s" % (sha[:7], rel),
                                        name + " (in history)", m.group(0)))
    return (len(commits), lines)


def audit(root: str = ".", as_json: bool = False, strict: bool = False,
          history: bool = False) -> int:
    root = os.path.abspath(root)
    files = _tracked_files(root)
    findings: list[Finding] = []
    for rel in files:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        _scan_path(rel, path, findings)
        _scan_text(rel, path, findings)

    hist_note = ""
    if history:
        n_commits, n_lines = _scan_history(root, findings)
        if n_commits:
            hist_note = "  [+ history: %d commits, %d added lines]" % (n_commits, n_lines)
            if n_commits < 2:
                hist_note += "  only 1 commit visible - shallow clone? push with full history"
        else:
            hist_note = "  [+ history: not a git repo, skipped]"

    order = ["1 secrets", "2 privacy", "3 abs paths", "4 temp files", "5 junk", "6 not public"]
    findings.sort(key=lambda f: (order.index(f.group), f.where))
    fails = [f for f in findings if f.level == "FAIL"]
    warns = [f for f in findings if f.level != "FAIL"]

    if as_json:
        print(json.dumps({"root": root, "files": len(files),
                          "fail": len(fails), "warn": len(warns),
                          "history": bool(history),
                          "findings": [f.as_dict() for f in findings]}, ensure_ascii=False, indent=2))
    else:
        print("auditing %s  (%d files)%s" % (root, len(files), hist_note))
        if not findings:
            print("  clean: no secrets, no personal data, no absolute paths, no junk")
        for group in order:
            items = [f for f in findings if f.group == group]
            if not items:
                continue
            print("\n%s" % group)
            for f in items:
                mark = "FAIL" if f.level == "FAIL" else "warn"
                print("  [%s] %-28s %s" % (mark, f.where, f.what))
                if f.detail:
                    print("         %s" % f.detail)
        print("\n%d blocking, %d to review" % (len(fails), len(warns)))
        if fails:
            print("\nfix the blocking items first. For a credential that was ever committed:")
            print("  rotate it, then rewrite history - deleting the line in a new commit is not enough.")
            print("  (that is what --history checks; a key that only ever lived in config.json is fine)")
    if fails:
        return 1
    if strict and warns:
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(audit(sys.argv[1] if len(sys.argv) > 1 else "."))
