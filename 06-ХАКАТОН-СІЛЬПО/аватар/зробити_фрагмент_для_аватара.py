#!/usr/bin/env python3
"""Фрагмент для навчання аватара: 30–90 с з довгого відео (Д184, хакатон Сільпо).

ЩО РОБИТЬ
  1) якщо дано посилання на YouTube — завантажує найкращу якість (yt-dlp);
  2) знаходить ділянку, де ГОВОРЯТЬ без довгих пауз (аналіз гучності ffmpeg,
     а не «перші 60 секунд» — на початку зазвичай заставка й тиша);
  3) ріже рівно 60 с (за замовчуванням) з перекодуванням у формат, який
     приймають сервіси аватарів: H.264 + AAC, 1080p максимум, 25–30 к/с;
  4) друкує паспорт фрагмента (тривалість, роздільність, звук, LUFS).

ВИКЛИК
  python зробити_фрагмент_для_аватара.py --url "https://youtu.be/..."
  python зробити_фрагмент_для_аватара.py --file "C:/шлях/відео.mp4" --seconds 60
  python зробити_фрагмент_для_аватара.py --file "..." --start 00:04:12 --seconds 75
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def probe(path: Path) -> dict:
    r = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format",
             "-show_streams", str(path)])
    return json.loads(r.stdout or "{}")


def download(url: str) -> Path:
    HERE.mkdir(parents=True, exist_ok=True)
    out = HERE / "джерело_%(id)s.%(ext)s"
    r = run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]",
             "--merge-output-format", "mp4", "-o", str(out), "--no-playlist", url])
    if r.returncode != 0:
        sys.exit(f"yt-dlp не впорався:\n{r.stderr[-1500:]}")
    files = sorted(HERE.glob("джерело_*.mp4"), key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit("завантажений файл не знайдено")
    return files[-1]


def find_speech_window(path: Path, seconds: int, scan_limit: int = 1800) -> float:
    """Вікно з найменшою кількістю тиші: беремо мапу тиші й шукаємо старт,
    де в наступні `seconds` секунд тиші найменше. Це груба, але чесна евристика —
    краще за «почати з нуля», де майже завжди заставка."""
    r = run([FFMPEG, "-hide_banner", "-nostats", "-t", str(scan_limit), "-i", str(path),
             "-af", "silencedetect=n=-32dB:d=0.7", "-f", "null", "-"])
    silences = []
    start = None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    dur = float(probe(path).get("format", {}).get("duration", 0))
    horizon = min(dur, scan_limit) - seconds
    if horizon <= 0:
        return 0.0

    def silence_in(t0: float) -> float:
        t1 = t0 + seconds
        return sum(max(0.0, min(t1, e) - max(t0, s)) for s, e in silences)

    # пропускаємо перші 10 с (заставки/титри), крок 5 с
    candidates = [t for t in range(10, int(horizon) + 1, 5)]
    if not candidates:
        return 0.0
    best = min(candidates, key=lambda t: (silence_in(t), t))
    return float(best)


def cut(src: Path, start: float, seconds: int, dst: Path) -> None:
    # -ss ПЕРЕД -i = швидкий пошук; перекодування — щоб перший кадр був ключовим
    r = run([FFMPEG, "-y", "-ss", f"{start:.2f}", "-i", str(src), "-t", str(seconds),
             "-vf", "scale='min(1920,iw)':-2:flags=lanczos,fps=30",
             "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", str(dst)])
    if r.returncode != 0:
        sys.exit(f"ffmpeg не впорався:\n{r.stderr[-1500:]}")


def passport(path: Path) -> str:
    info = probe(path)
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), {})
    a = next((s for s in info.get("streams", []) if s["codec_type"] == "audio"), {})
    dur = float(info.get("format", {}).get("duration", 0))
    size = path.stat().st_size / 1e6
    loud = run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path),
                "-af", "ebur128=framelog=quiet", "-f", "null", "-"]).stderr
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", loud)
    return (f"{path.name}: {dur:.1f} с · {v.get('width')}×{v.get('height')} · "
            f"{v.get('codec_name')}/{a.get('codec_name','БЕЗ ЗВУКУ')} · {size:.1f} МБ"
            + (f" · гучність {m.group(1)} LUFS" if m else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="посилання на YouTube")
    ap.add_argument("--file", type=Path, help="готовий файл на диску")
    ap.add_argument("--seconds", type=int, default=60, help="довжина фрагмента (30–90)")
    ap.add_argument("--start", help="час початку ГГ:ХХ:СС (якщо не задано — знайду сам)")
    ap.add_argument("--name", default="аватар-джерело", help="назва вихідного файлу")
    a = ap.parse_args()
    if not (a.url or a.file):
        ap.error("дай --url або --file")
    if not 15 <= a.seconds <= 120:
        ap.error("розумна довжина для аватара — 30–90 с")

    src = download(a.url) if a.url else a.file.resolve()
    if not src.exists():
        sys.exit(f"немає файлу: {src}")
    print("джерело:", passport(src))

    if a.start:
        h, m, s = (a.start.split(":") + ["0", "0"])[:3] if ":" in a.start else ("0", "0", a.start)
        start = int(h) * 3600 + int(m) * 60 + float(s)
    else:
        print("шукаю ділянку з мовленням (не заставку)…")
        start = find_speech_window(src, a.seconds)
    print(f"початок фрагмента: {int(start//60):02d}:{int(start%60):02d}")

    dst = HERE / f"{a.name}_{a.seconds}с.mp4"
    cut(src, start, a.seconds, dst)
    print("готово:", passport(dst))
    print("файл:", dst)


if __name__ == "__main__":
    main()
