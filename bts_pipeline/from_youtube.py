#!/usr/bin/env python3
"""YouTube URL -> extract source screenshots for BTS generation.

Pipeline (free tools only):
  1. yt-dlp / ffmpeg grab the video
  2. Extract 10 unique screenshots (active picture only, no letterbox)
  3. Generate photoreal BTS stills from each screenshot (GenerateImage)
  4. animate_bts_stills.py turns those stills into 5s 1080x1920 Shorts
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

YT_DLP = shutil.which("yt-dlp") or str(Path.home() / ".local/bin/yt-dlp")
FFMPEG = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/usr/bin/ffprobe"
DENO = shutil.which("deno") or str(Path.home() / ".local/bin/deno")

OUT_W, OUT_H, CLIP_SEC = 1080, 1920, 5


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path: Path):
    raw = subprocess.check_output(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-of",
            "json",
            str(path),
        ]
    )
    s = json.loads(raw)["streams"][0]
    dur = float(s.get("duration") or 0)
    if not dur:
        fmt = json.loads(
            subprocess.check_output(
                [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
            )
        )
        dur = float(fmt["format"].get("duration") or 0)
    return int(s["width"]), int(s["height"]), dur


def crop_916_vf(w: int, h: int, xfrac: float = 0.5) -> str:
    """Non-generative 9:16 crop, then scale to 1080x1920. Never pad."""
    if w / h <= 9 / 16 + 0.01:
        crop_w = w - (w % 2)
        crop_h = int(crop_w * 16 / 9)
        crop_h -= crop_h % 2
        if crop_h > h:
            crop_h = h - (h % 2)
            crop_w = int(crop_h * 9 / 16)
            crop_w -= crop_w % 2
        x = max(0, int((w - crop_w) * xfrac))
        y = max(0, int((h - crop_h) * 0.35))
    else:
        crop_h = h - (h % 2)
        crop_w = int(crop_h * 9 / 16)
        crop_w -= crop_w % 2
        x = max(0, int((w - crop_w) * xfrac))
        y = 0
    x -= x % 2
    y -= y % 2
    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1,fps=24,format=yuv420p"


def download_youtube(url: str, dest: Path, cookies: Path | None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest / "source.%(ext)s")
    cmd = [
        YT_DLP,
        "--no-warnings",
        "--no-playlist",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format",
        "mp4",
        "-o",
        outtmpl,
    ]
    if Path(DENO).exists():
        cmd += ["--js-runtimes", f"deno:{DENO}"]
    if cookies and cookies.exists():
        cmd += ["--cookies", str(cookies)]
    cmd.append(url)
    env = os.environ.copy()
    env["PATH"] = str(Path(DENO).parent) + os.pathsep + env.get("PATH", "")
    run(cmd, env=env)
    files = list(dest.glob("source.*"))
    if not files:
        raise SystemExit("yt-dlp finished but no source file was written")
    return files[0]


def pick_starts(duration: float, n: int = 10) -> list[float]:
    usable = max(duration - CLIP_SEC, 0.1)
    margin = min(2.0, usable * 0.06)
    lo, hi = margin, max(margin, usable - margin)
    if hi <= lo:
        return [0.0] * n
    span = hi - lo
    return [lo + span * (i + 0.5) / n for i in range(n)]


def encode_clip(src: Path, dst: Path, start: float, vf: str):
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(src),
            "-t",
            str(CLIP_SEC),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-movflags",
            "+faststart",
            str(dst),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="bts_output")
    p.add_argument("--cache", default="bts_pipeline/.cache")
    p.add_argument("--cookies", default=os.environ.get("YOUTUBE_COOKIES_FILE", ""))
    args = p.parse_args()

    out = Path(args.out)
    cache = Path(args.cache)
    out.mkdir(parents=True, exist_ok=True)
    cookies = Path(args.cookies) if args.cookies else None

    print("downloading", args.url, file=sys.stderr)
    source = download_youtube(args.url, cache / "source", cookies)
    w, h, dur = probe(source)
    print(f"source {w}x{h} {dur:.1f}s", file=sys.stderr)
    starts = pick_starts(dur)
    vf = crop_916_vf(w, h, 0.5)

    for i, start in enumerate(starts, 1):
        num = f"{i:02d}"
        dst = out / f"VIDEO_{num}.mp4"
        encode_clip(source, dst, start, vf)
        ow, oh, od = probe(dst)
        print(f"VIDEO_{num} {ow}x{oh} {od:.3f}s start={start:.2f}", file=sys.stderr)
        if ow != OUT_W or oh != OUT_H:
            raise SystemExit(f"VIDEO_{num} is not 1080x1920")

    thumb_src = out / "THUMBNAIL_SOURCE.jpg"
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            f"{starts[2] + 1:.3f}",
            "-i",
            str(out / "VIDEO_03.mp4"),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(thumb_src),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(json.dumps({"ok": True, "source_duration": dur, "out": str(out)}))


if __name__ == "__main__":
    main()
