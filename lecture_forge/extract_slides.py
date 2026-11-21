"""Stage 3 - pull the slides out of the video.

Screen-recorded lectures are mostly one static slide per minute, so the cheap
way to get figures is: find the frames where the picture *changes a lot*, keep
one per change, then crop the slide area and upscale it.

Two details make the output usable:

* ``--min-interval`` stops animations (a cursor moving, a line being drawn)
  from producing ten near-identical frames a second;
* the crop is driven by brightness, because a screen recording usually has
  black bars or a desktop around the slide.
"""

from __future__ import annotations

import os

from .util import die, ensure_dir, info, warn


def extract(video: str, outdir: str, min_interval: float = 8.0, threshold: float = 0.004,
            scale: float = 2.0, crop: bool = True, max_width: int = 1600) -> list[str]:
    try:
        import av
        from PIL import Image, ImageFilter
    except Exception:
        die("this stage needs `av` and `pillow`:\n  python -m pip install -U av pillow")
        raise
    if not os.path.isfile(video):
        die("video not found: %s" % video)
    ensure_dir(outdir)

    container = av.open(video)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    tb = float(stream.average_rate or 12)

    saved, last_t, last_small = [], -1e9, None
    for frame in container.decode(stream):
        t = float(frame.pts * stream.time_base)
        if t - last_t < min_interval:
            continue
        img = frame.to_image().convert("L")
        small = img.resize((64, 40), Image.BILINEAR)
        if last_small is not None:
            diff = sum(abs(a - b) for a, b in zip(small.tobytes(), last_small.tobytes()))
            changed = diff / (64 * 40 * 255.0) > threshold
            if not changed:
                continue
        last_small = small
        last_t = t
        shot = frame.to_image().convert("RGB")
        if crop:
            shot = _crop_slide(shot)
        shot = _upscale(shot, scale, max_width)
        name = "t%05d.png" % int(t)
        shot.save(os.path.join(outdir, name), optimize=True)
        saved.append(os.path.join(outdir, name))
        info("  %s  (%.1fs)" % (name, t))
    container.close()
    info("%d frames -> %s" % (len(saved), outdir))
    if not saved:
        warn("no keyframe found; lower --threshold or drop --min-interval")
    return saved


def _crop_slide(img, pad: int = 4):
    """Crop the brightest large rectangle (the slide), if it is big enough."""
    from PIL import Image, ImageFilter

    w, h = img.size
    g = img.convert("L").filter(ImageFilter.GaussianBlur(2))
    px = g.load()
    rows = [max(px[x, y] for x in range(0, w, max(1, w // 60))) for y in range(h)]
    cols = [max(px[x, y] for y in range(0, h, max(1, h // 60))) for x in range(w)]
    if not rows or not cols:
        return img
    rt = max(rows) * 0.35
    ct = max(cols) * 0.35
    ys = [y for y, v in enumerate(rows) if v > rt]
    xs = [x for x, v in enumerate(cols) if v > ct]
    if not xs or not ys:
        return img
    box = (max(0, xs[0] - pad), max(0, ys[0] - pad), min(w, xs[-1] + pad), min(h, ys[-1] + pad))
    if (box[2] - box[0]) * (box[3] - box[1]) < 0.4 * w * h:
        return img  # crop would throw away most of the frame -> keep as is
    return img.crop(box)


def _upscale(img, scale: float, max_width: int):
    from PIL import Image, ImageFilter

    w, h = img.size
    tw = min(int(w * scale), max_width)
    if tw <= w:
        return img
    out = img.resize((tw, int(h * tw / w)), Image.LANCZOS)
    return out.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=3))
