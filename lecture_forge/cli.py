"""Command line entry point: python -m lecture_forge <stage> ...

Each stage is independent, so an agent can run exactly one of them, inspect
the result, and continue:

    fetch      URL or local file        -> work/audio.*  work/video.*
    transcribe audio                    -> work/audio.txt|srt|jsonl
    slides     video                    -> work/slides/*.png
    build      lecture folder           -> site/ (index.html + ask.html + img/)
    serve      site + config            -> http://127.0.0.1:8765/
    audit      any folder               -> the six pre-publish checks

`python -m lecture_forge -h` prints the same list.
"""

from __future__ import annotations

import argparse
import os

from . import __version__
from .util import info, load_config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="lecture_forge",
        description="Turn a video or a document into a lecture you can question.")
    p.add_argument("--version", action="version", version="lecture-forge " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download the media (or copy a local file)")
    f.add_argument("source", help="URL, or a local file")
    f.add_argument("-o", "--outdir", default="work")
    f.add_argument("--no-video", action="store_true", help="audio only (skip the slide source)")

    t = sub.add_parser("transcribe", help="speech -> timestamped text")
    t.add_argument("audio")
    t.add_argument("-o", "--outdir", default="work")
    t.add_argument("-c", "--config", default=None)

    s = sub.add_parser("slides", help="pull slide frames out of the video")
    s.add_argument("video")
    s.add_argument("-o", "--outdir", default="work/slides")
    s.add_argument("--min-interval", type=float, default=8.0, help="seconds between kept frames")
    s.add_argument("--threshold", type=float, default=0.004, help="how much the frame must change")
    s.add_argument("--scale", type=float, default=2.0)
    s.add_argument("--no-crop", action="store_true")

    b = sub.add_parser("build", help="build the static site from a lecture folder")
    b.add_argument("src", help="folder with lecture.md / meta.json / qa-bank.json / img/")
    b.add_argument("-o", "--outdir", default="site")
    b.add_argument("--embed", action="store_true", help="inline the images (single shareable file)")
    b.add_argument("-c", "--config", default=None)

    v = sub.add_parser("serve", help="serve the site and the /ask endpoint")
    v.add_argument("-c", "--config", default=None)

    a = sub.add_parser("audit", help="pre-publish safety check")
    a.add_argument("root", nargs="?", default=".")
    a.add_argument("--json", action="store_true")
    a.add_argument("--strict", action="store_true", help="warnings fail too")

    d = sub.add_parser("doctor", help="diagnose the environment (why won't it start?)")
    d.add_argument("-c", "--config", default=None)
    d.add_argument("--root", default=".")

    args = p.parse_args(argv)

    if args.cmd == "doctor":
        from .doctor import doctor

        return doctor(args.config, args.root)


    if args.cmd == "fetch":
        from .fetch_media import fetch

        res = fetch(args.source, args.outdir, video=not args.no_video)
        info("next: python -m lecture_forge transcribe %s -o %s" % (res["audio"], args.outdir))
        return 0

    if args.cmd == "transcribe":
        from .transcribe import transcribe

        transcribe(args.audio, args.outdir, load_config(args.config))
        return 0

    if args.cmd == "slides":
        from .extract_slides import extract

        extract(args.video, args.outdir, min_interval=args.min_interval,
                threshold=args.threshold, scale=args.scale, crop=not args.no_crop)
        return 0

    if args.cmd == "build":
        from .build_site import build

        build(args.src, args.outdir, load_config(args.config), embed=args.embed)
        return 0

    if args.cmd == "serve":
        from .serve import serve

        serve(args.config)
        return 0

    if args.cmd == "audit":
        from .audit import audit as run_audit

        return run_audit(args.root, as_json=args.json, strict=args.strict)

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
