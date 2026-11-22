# -*- coding: utf-8 -*-
"""Self-test for `audit --history`.

The point of `--history` is the case people get wrong: a key pasted into a
commit, then deleted in a later commit. The working tree looks clean, but the
blob is still in the repo and is still downloaded by every clone.

Usage:  python tests/history_selftest.py
Exit:   0 = behaves as documented, 1 = regression
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lecture_forge.audit import audit  # noqa: E402


def _rm(path):
    def _force(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onerror=_force)


def build_leaky_repo() -> str:
    t = tempfile.mkdtemp(prefix="lf_hist_")
    def g(*a):
        subprocess.run(["git", "-C", t] + list(a), check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "selftest@example.com")
    g("config", "user.name", "selftest")
    with open(os.path.join(t, "a.txt"), "w", encoding="utf-8") as f:
        f.write("hello\n")
    g("add", "-A")
    g("commit", "-qm", "one")

    with open(os.path.join(t, "leak.py"), "w", encoding="utf-8") as f:
        f.write('KEY = "sk-%s"\n' % ("A" * 24))
    g("add", "-A")
    g("commit", "-qm", "two: paste a key")

    os.remove(os.path.join(t, "leak.py"))
    g("add", "-A")
    g("commit", "-qm", "three: delete it again")
    return t


def main() -> int:
    ok = True
    t = build_leaky_repo()
    try:
        rc_tree = audit(t, history=False)
        rc_hist = audit(t, history=True)
        checks = [
            ("working tree looks clean", rc_tree == 0),
            ("history blocks on the deleted key", rc_hist == 1),
        ]
        for name, passed in checks:
            print("PASS  " + name if passed else "FAIL  " + name)
            ok = ok and passed
    finally:
        _rm(t)

    print("selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
