"""Сборка слайд-шоу через ffmpeg. Процессы запускаются асинхронно, число одновременных
процессов ограничено семафором — бот не зависает при нагрузке."""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import config

log = logging.getLogger(__name__)

# ключ → (ширина, высота)
RATIOS: dict[str, tuple[int, int]] = {
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
}
FPS = 30  # 0.1/0.2/0.3/0.5/0.8/1.0 сек дают целое число кадров при 30 fps


class FFmpegError(RuntimeError):
    pass


@dataclass
class SlideshowSettings:
    duration: int  # общая длина, сек
    interval: float  # сколько секунд показывается одно фото
    ratio: str  # ключ из RATIOS
    filter: str = "none"  # none | bw
    brightness: int = 100  # 10..100 (%)


_sem: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(config.MAX_PARALLEL_FFMPEG)
    return _sem


async def _run_ffmpeg(*args: str, timeout: int | None = None) -> None:
    timeout = timeout or config.FFMPEG_TIMEOUT
    async with _semaphore():
        proc = await asyncio.create_subprocess_exec(
            config.FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise FFmpegError(f"ffmpeg timeout ({timeout}s)")
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
    if proc.returncode != 0:
        msg = err.decode("utf-8", "ignore")[-1500:]
        log.error("ffmpeg failed: %s", msg)
        raise FFmpegError(msg)


# ───────────────────────── Слайд-шоу ─────────────────────────
async def prepare_frames(sources: list[Path], ratio: str, out_dir: Path) -> list[Path]:
    """Каждое фото → jpg нужного размера (cover + центральный кроп).
    Для 16:9 это и есть «полоса из центра фото»."""
    w, h = RATIOS[ratio]
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={w}:{h},setsar=1"
    )

    async def one(i: int, src: Path) -> Path:
        out = out_dir / f"frame_{i:02d}.jpg"
        await _run_ffmpeg("-i", str(src), "-vf", vf, "-frames:v", "1", "-q:v", "2", str(out))
        return out

    return list(await asyncio.gather(*(one(i, s) for i, s in enumerate(sources))))


async def render_slideshow(
    frames: list[Path], s: SlideshowSettings, out_path: Path, tag: str = "main"
) -> Path:
    """Нарезка кадров по interval и зацикливание до duration.
    frames должны лежать в той же папке, что и out_path (concat использует относительные имена)."""
    list_path = out_path.parent / f"list_{tag}.txt"
    n = math.ceil(s.duration / s.interval) + 1
    lines = ["ffconcat version 1.0"]
    last = frames[0]
    for i in range(n):
        last = frames[i % len(frames)]
        lines += [f"file '{last.name}'", f"duration {s.interval:.3f}"]
    lines.append(f"file '{last.name}'")  # concat игнорирует duration последнего файла
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    vf: list[str] = []
    if s.filter == "bw":
        vf.append("hue=s=0")
    if s.brightness < 100:
        k = round(s.brightness / 100, 3)
        vf.append(f"colorchannelmixer=rr={k}:gg={k}:bb={k}")
    vf += [f"fps={FPS}", "format=yuv420p"]

    await _run_ffmpeg(
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-vf", ",".join(vf),
        "-t", str(s.duration),
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-movflags", "+faststart",
        str(out_path),
    )
    return out_path


async def build_slideshow(sources: list[Path], s: SlideshowSettings, job_dir: Path) -> Path:
    frames = await prepare_frames(sources, s.ratio, job_dir)
    return await render_slideshow(frames, s, job_dir / "result.mp4")
