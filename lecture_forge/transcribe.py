"""Stage 2 - speech to text with timestamps.

Uses faster-whisper.  Outputs three files next to each other:

* ``<stem>.txt``    one segment per line, prefixed with ``[mm:ss -> mm:ss]``
* ``<stem>.srt``    a normal subtitle file (handy for a video player)
* ``<stem>.jsonl``  one JSON object per segment (machine friendly)

``initial_prompt`` matters more than any other option here: feeding the
domain vocabulary ("mesh current", "nodal analysis", the names your course
uses) measurably cuts the number of homophone errors on Chinese technical
lectures.
"""

from __future__ import annotations

import json
import os
import sys

from .util import die, info, mmss, warn


def _harden_windows_cuda() -> None:
    """faster-whisper needs the nvidia DLL folders on PATH under Windows."""
    if os.name != "nt":
        return
    try:
        import site

        for root in site.getsitepackages() + [site.getusersitepackages()]:
            nv = os.path.join(root, "nvidia")
            if not os.path.isdir(nv):
                continue
            for pkg in os.listdir(nv):
                for sub in ("bin", "lib"):
                    d = os.path.join(nv, pkg, sub)
                    if os.path.isdir(d):
                        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                        if hasattr(os, "add_dll_directory"):
                            try:
                                os.add_dll_directory(d)
                            except OSError:
                                pass
    except Exception as e:  # pragma: no cover - best effort only
        warn("could not extend PATH for CUDA libraries: %s" % e)


def _load(cfg: dict):
    try:
        from faster_whisper import WhisperModel
    except Exception:
        die(
            "faster-whisper is not installed.\n"
            "  python -m pip install -U faster-whisper\n"
            "  (a GPU is optional; on CPU it still works, just slower)"
        )
        raise
    _harden_windows_cuda()
    asr = cfg.get("asr", {})
    name = asr.get("model", "large-v3")
    extra = {}
    # China-friendly: reuse a model folder you already downloaded instead of
    # hitting huggingface.co every time.  `asr.model` may also be a local dir.
    if asr.get("download_root"):
        extra["download_root"] = os.path.expanduser(asr["download_root"])
    if asr.get("local_files_only"):
        extra["local_files_only"] = True
    device = asr.get("device", "auto")
    compute = asr.get("compute_type", "auto")
    attempts = []
    if device == "auto":
        attempts = [("cuda", "float16" if compute == "auto" else compute), ("cpu", "int8" if compute == "auto" else compute)]
    else:
        attempts = [(device, compute if compute != "auto" else ("float16" if device == "cuda" else "int8"))]
    last = None
    for dev, ct in attempts:
        try:
            info("loading whisper model %r on %s/%s ..." % (name, dev, ct))
            return WhisperModel(name, device=dev, compute_type=ct, **extra)
        except Exception as e:
            last = e
            warn("cannot use %s/%s (%s); trying the next option" % (dev, ct, str(e)[:120]))
    die("no usable whisper device: %s" % last)
    raise SystemExit(1)


def _decode_audio(path: str, rate: int = 16000):
    """Decode any media file to mono float32 @16 kHz ourselves.

    faster-whisper ships its own decoder, but it calls
    ``av.open(..., metadata_errors="ignore")`` — a keyword newer PyAV builds
    (>= 15) no longer accept, which makes the whole stage explode with
    ``TypeError: open() got an unexpected keyword argument 'metadata_errors'``.
    Decoding here keeps us independent of that internal API.
    """
    import av
    import numpy as np

    with av.open(path) as container:
        if not container.streams.audio:
            raise RuntimeError("no audio stream in %s" % os.path.basename(path))
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=rate)
        chunks = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                buf = out.to_ndarray()
                if buf.ndim == 2:
                    buf = buf[0] if buf.shape[0] == 1 else buf.mean(axis=0)
                chunks.append(np.ascontiguousarray(buf, dtype=np.float32))
        for out in resampler.resample(None):
            buf = out.to_ndarray()
            if buf.ndim == 2:
                buf = buf[0] if buf.shape[0] == 1 else buf.mean(axis=0)
            chunks.append(np.ascontiguousarray(buf, dtype=np.float32))
    if not chunks:
        raise RuntimeError("decoded no audio from %s" % os.path.basename(path))
    return np.concatenate(chunks)


def transcribe(audio: str, outdir: str, cfg: dict) -> dict:
    if not audio or not os.path.isfile(audio):
        die("audio file not found: %s" % audio)
    model = _load(cfg)
    asr = cfg.get("asr", {})
    info("transcribing %s (this is the slow part) ..." % os.path.basename(audio))
    try:
        feed = _decode_audio(audio)
    except Exception as e:
        warn("own decoder failed (%s); letting faster-whisper decode the file" % str(e)[:120])
        feed = audio
    segments, meta = model.transcribe(
        feed,
        language=asr.get("language") or None,
        vad_filter=True,
        beam_size=int(asr.get("beam_size", 5)),
        initial_prompt=asr.get("initial_prompt") or None,
        condition_on_previous_text=False,
    )
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(audio))[0]

    lines, srt, rows = [], [], []
    for i, seg in enumerate(segments, 1):
        text = seg.text.strip()
        if not text:
            continue
        lines.append("[%s -> %s] %s" % (mmss(seg.start), mmss(seg.end), text))
        srt.append("%d\n%s --> %s\n%s\n" % (i, _srt_ts(seg.start), _srt_ts(seg.end), text))
        rows.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
        if i % 50 == 0:
            info("  %d segments, at %s" % (i, mmss(seg.end)))

    txt_p = os.path.join(outdir, stem + ".txt")
    with open(txt_p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(outdir, stem + ".srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    with open(os.path.join(outdir, stem + ".jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    info("done: %d segments, duration %s -> %s" % (len(rows), mmss(getattr(meta, "duration", 0)), txt_p))
    return {"txt": txt_p, "srt": os.path.join(outdir, stem + ".srt"),
            "jsonl": os.path.join(outdir, stem + ".jsonl"), "segments": len(rows)}


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


if __name__ == "__main__":  # pragma: no cover
    sys.exit("run it through the CLI: python -m lecture_forge transcribe <audio>")
