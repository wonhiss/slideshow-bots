"""Настройки бота: токен и спонсорские каналы — здесь (или токен в .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv не обязателен
    pass

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"  # temp/{user_id}/...

# ── 1. ТОКЕН БОТА ────────────────────────────────────────────────────────────
# Вставьте токен от @BotFather сюда ИЛИ задайте переменную BOT_TOKEN в .env
BOT_TOKEN = os.getenv("BOT_TOKEN", "8791562417:AAHd1Bc-llGG982DYj4iaxGo_Qe1vwi5tvs")

ADMIN_IDS: set[int] = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}


# ── 2. СПОНСОРСКИЕ КАНАЛЫ (ОП) ───────────────────────────────────────────────
@dataclass(frozen=True)
class Sponsor:
    title: str  # текст на кнопке
    chat_id: int | str  # "@username" публичного канала или -100... для приватного
    url: str  # ссылка на кнопке (публичная или invite-ссылка)


# ВАЖНО: бот должен быть администратором в каждом канале, иначе Telegram не даст
# проверить подписку. Пустой список = проверка отключена.
SPONSORS: list[Sponsor] = [
    Sponsor("📣 Подпишись на наш канал", -1004464759244, "https://t.me/+wu7M4Wmg_8szZDdi"),]
    # Sponsor("🔒 Приватный канал", -1001234567890, "https://t.me/+AbCdEfGh"),]
SUB_CACHE_TTL = 60  # сек: кэш успешной проверки

# ── 3. ffmpeg и отправка ─────────────────────────────────────────────────────
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
MAX_PARALLEL_FFMPEG = int(os.getenv("MAX_PARALLEL_FFMPEG", "2"))
FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "180"))
SEND_AS_DOCUMENT = os.getenv("SEND_AS_DOCUMENT", "0") == "1"

# ── 4. Опции конструктора ────────────────────────────────────────────────────
MIN_PHOTOS = 2
MAX_PHOTOS = 5
DURATIONS = [5, 6, 7, 8, 10, 12, 15]
INTERVALS = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0]
BRIGHTNESS = [100, 80, 60, 40, 10]
