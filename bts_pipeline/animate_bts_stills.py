#!/usr/bin/env python3
"""Screenshot BTS stills -> 10x 5s true 9:16 Shorts + 1 thumbnail.

Generated stills are 1024x1536 (2:3). Center-crop to 9:16, then handheld-animate
so the clip feels like a PA filming the take, not a Ken Burns poster.
Never pad; never letterbox.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FFMPEG = "/usr/bin/ffmpeg"
FFPROBE = "/usr/bin/ffprobe"
OUT_W, OUT_H, FPS, NFRAMES = 1080, 1920, 24, 120
STILL_DIR = Path("/tmp/bts2/bts_stills")
WORK = Path("/tmp/bts2/work_anim")
OUT = Path("/workspace/bts_output")
ART = Path("/opt/cursor/artifacts")
QA = Path("/tmp/bts2/qa")

# 1024x1536 -> 864x1536 (true 9:16) then scale
CROP_916 = "crop=864:1536:80:0,scale=1080:1920:flags=lanczos,setsar=1"

STILLS = [
    "bts_01.png",
    "bts_02.png",
    "bts_03.png",
    "bts_04.png",
    "bts_05.png",
    "bts_06.png",
    "bts_07.png",
    "bts_08.png",
    "bts_09.png",
    "bts_10.png",
]

# Unique observer-camera moves. Expressions are in output pixels after
# scaling the 1080x1920 plate larger, then cropping back.
MOTIONS = [
    # 1 Doom throne: slow push in, standing handheld
    "scale=w='1080*(1.06+0.10*t/5)':h='1920*(1.06+0.10*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+10*sin(2*PI*t/1.35):(in_h-1920)/2+7*sin(2*PI*t/0.92)",
    # 2 wounded elder: push-in + handheld breathe
    "scale=w='1080*(1.08+0.10*t/5)':h='1920*(1.08+0.10*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+14*sin(2*PI*t/1.12)+7*sin(2*PI*t/0.47):"
    "(in_h-1920)/2+11*sin(2*PI*t/0.88)+6*sin(2*PI*t/0.41)",
    # 3 Reed profile: pan with the look (left)
    "scale=1242:2208,"
    "crop=1080:1920:max(0\\,in_w-1080-6-78*t/5)+7*sin(2*PI*t/1.6):"
    "(in_h-1920)/2+8*sin(2*PI*t/1.25)",
    # 4 Wakanda group: slow push + lateral drift
    "scale=w='1080*(1.04+0.09*t/5)':h='1920*(1.04+0.09*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+18*t/5+6*sin(2*PI*t/1.7):(in_h-1920)/2+5*sin(2*PI*t/1.1)",
    # 5 ruined city volume: crane-up feel
    "scale=1210:2152,"
    "crop=1080:1920:(in_w-1080)/2+8*sin(2*PI*t/1.8):"
    "max(0\\,in_h-1920-8-70*t/5)+6*sin(2*PI*t/1.4)",
    # 6 father/child: gentle push, softer shake
    "scale=w='1080*(1.03+0.07*t/5)':h='1920*(1.03+0.07*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+6*sin(2*PI*t/1.9):(in_h-1920)/2+5*sin(2*PI*t/1.5)",
    # 7 Cyclops: aggressive handheld push on the take
    "scale=w='1080*(1.07+0.11*t/5)':h='1920*(1.07+0.11*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+16*sin(2*PI*t/0.95)+8*sin(2*PI*t/0.38):"
    "(in_h-1920)/2+12*sin(2*PI*t/0.72)+7*sin(2*PI*t/0.33)",
    # 8 Thor: push + shake matching energy
    "scale=w='1080*(1.05+0.12*t/5)':h='1920*(1.05+0.12*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+12*sin(2*PI*t/1.05)+5*sin(2*PI*t/0.4):"
    "(in_h-1920)/2+9*sin(2*PI*t/0.82)",
    # 9 Doom from behind: pan right across set
    "scale=1260:2240,"
    "crop=1080:1920:min(in_w-1080\\,8+90*t/5)+6*sin(2*PI*t/1.55):"
    "(in_h-1920)/2+7*sin(2*PI*t/1.3)",
    # 10 masked hero: slow pull back (reveal more crew)
    "scale=w='1080*(1.16-0.10*t/5)':h='1920*(1.16-0.10*t/5)':eval=frame,"
    "crop=1080:1920:(in_w-1080)/2+8*sin(2*PI*t/1.45):(in_h-1920)/2+6*sin(2*PI*t/1.15)",
]

LIVE_GRADE = (
    "eq=brightness='0.012*sin(2*PI*t/0.85)':contrast=1.03:saturation=1.04,"
    "noise=alls=3:allf=t+u"
)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def encode_clip(i: int):
    n = f"{i:02d}"
    src = STILL_DIR / STILLS[i - 1]
    dst = OUT / f"VIDEO_{n}.mp4"
    qa = QA / f"v{n}.jpg"
    if not src.exists():
        raise SystemExit(f"missing still {src}")
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    vf = (
        f"{CROP_916},{MOTIONS[i - 1]},"
        f"{LIVE_GRADE},fps={FPS},format=yuv420p"
    )
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-framerate", str(FPS), "-t", "5.2", "-i", str(src),
        "-vf", vf,
        "-r", str(FPS),
        "-frames:v", str(NFRAMES),
        "-t", "5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(dst),
    ]
    print(f"anim {n} <- {src.name}", file=sys.stderr)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode()[-4000:])
        raise SystemExit(f"encode failed {n}")

    run(
        [FFMPEG, "-y", "-ss", "2.2", "-i", str(dst), "-frames:v", "1", "-q:v", "2", str(qa)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    probe = subprocess.check_output(
        [
            FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames,duration",
            "-of", "csv=p=0", str(dst),
        ]
    ).decode().strip()
    print(f"VIDEO_{n} {probe} {dst.stat().st_size}", file=sys.stderr)
    ART.mkdir(parents=True, exist_ok=True)
    run(["cp", str(dst), str(ART / f"doomsday_bts_{n}.mp4")])


def make_thumbnail():
    """CTR crop from the strongest character BTS still (front Doom + crew)."""
    src = STILL_DIR / "bts_10.png"
    dst = OUT / "THUMBNAIL.png"
    # Tighter 9:16 on the masked figure, punch contrast.
    vf = (
        "crop=792:1408:116:40,scale=1080:1920:flags=lanczos,setsar=1,"
        "eq=contrast=1.10:saturation=1.14:brightness=0.03,unsharp=5:5:0.7:5:5:0.0"
    )
    run(
        [FFMPEG, "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", str(dst)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    run(["cp", str(dst), str(ART / "doomsday_thumb_916.png")])
    print(f"THUMBNAIL {dst.stat().st_size}", file=sys.stderr)


def main():
    for i in range(1, 11):
        encode_clip(i)
    make_thumbnail()
    print("done")


if __name__ == "__main__":
    main()
