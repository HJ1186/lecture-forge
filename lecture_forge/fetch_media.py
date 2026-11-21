"""Stage 1 - get the media.

Two inputs are supported:

* a URL  -> downloaded with yt-dlp (audio for ASR, plus a small video for slides)
* a file -> copied/linked as-is (local mp4 / m4a / mp3 / wav / mp4 of a screen recording)

The stage refuses to run if yt-dlp is missing, and tells the user exactly how to
install it, instead of failing halfway through a download.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .util import die, ensure_dir, human_size, info, warn


def _ytdlp() -> list[str]:
    """Return the argv prefix that runs yt-dlp, or exit with instructions."""
    exe = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        die(
            "yt-dlp not found.\n"
            "  install it with:  python -m pip install -U yt-dlp\n"
            "  or point $YTDLP_PATH at the executable."
        )
    return []  # unreachable


def fetch(url: str, outdir: str, video: bool = True, quiet: bool = False) -> dict:
    """Download `url` (or copy a local file) into `outdir`.

    Returns {"audio": path|None, "video": path|None, "source": str}.
    """
    ensure_dir(outdir)
    if not url.lower().startswith(("http://", "https://")):
        if not os.path.isfile(url):
            die("not a URL and not an existing file: %s" % url)
        dst = os.path.join(outdir, os.path.basename(url))
        if os.path.abspath(dst) != os.path.abspath(url):
            shutil.copy2(url, dst)
        info("local file -> %s (%s)" % (dst, human_size(os.path.getsize(dst))))
        return {"audio": dst, "video": dst, "source": url}

    pre = _ytdlp()
    audio_fmt = os.path.join(outdir, "audio.%(ext)s")
    cmd = pre + [
        "-f", "bestaudio/best",
        "--no-playlist",
        "-o", audio_fmt,
        "--print", "after_move:filepath",
        url,
    ]
    if not quiet:
        info("downloading audio ...")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        warn((res.stderr or "").strip()[-800:])
        die("yt-dlp failed on the audio stream")
    audio = (res.stdout or "").strip().splitlines()[-1] if res.stdout.strip() else None
    if audio and not os.path.isfile(audio):
        audio = None
    info("audio  -> %s (%s)" % (audio, human_size(os.path.getsize(audio)) if audio else "?"))

    video_path = None
    if video:
        # 720p cap keeps the frame count (and the CPU bill) reasonable.
        video_fmt = os.path.join(outdir, "video.%(ext)s")
        cmd = pre + [
            "-f", "bv*[height<=720]/b[height<=720]/b",
            "--no-playlist",
            "-o", video_fmt,
            "--print", "after_move:filepath",
            url,
        ]
        if not quiet:
            info("downloading video (for slide frames) ...")
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0 and res.stdout.strip():
            video_path = res.stdout.strip().splitlines()[-1]
            if not os.path.isfile(video_path):
                video_path = None
        if video_path:
            info("video  -> %s (%s)" % (video_path, human_size(os.path.getsize(video_path))))
        else:
            warn("video stream not available; slides will have to come from elsewhere")
    return {"audio": audio, "video": video_path, "source": url}
