"""Все инлайн-клавиатуры бота."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

import config
from config import Sponsor

RATIO_BUTTONS = {"9x16": "📱 9:16", "16x9": "💻 16:9", "1x1": "⏹ 1:1", "4x5": "📸 4:5"}
FILTER_BUTTONS = {"none": "🌈 Без фильтра", "bw": "🔳 Чёрно-белый (B&W)"}


def _kb(rows: list[list[Btn]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _chunk(buttons: list[Btn], n: int) -> list[list[Btn]]:
    return [buttons[i : i + n] for i in range(0, len(buttons), n)]


def _nav(back: bool) -> list[Btn]:
    row = []
    if back:
        row.append(Btn(text="⬅️ Назад", callback_data="ss:back"))
    row.append(Btn(text="❌ Отмена", callback_data="ss:cancel"))
    return row


# ── Подписка и приветствие ───────────────────────────────────────────────────
def sponsors_kb(sponsors: list[Sponsor]) -> InlineKeyboardMarkup:
    rows = [[Btn(text=s.title, url=s.url)] for s in sponsors]
    rows.append([Btn(text="✅ Проверить подписку", callback_data="check_sub")])
    return _kb(rows)


def welcome_kb() -> InlineKeyboardMarkup:
    return _kb([[Btn(text="🎬 Создать слайд-шоу", callback_data="ss:new")]])


# ── Загрузка фото ────────────────────────────────────────────────────────────
def photos_kb(count: int = 0) -> InlineKeyboardMarkup:
    rows = []
    if count >= config.MIN_PHOTOS:
        rows.append([Btn(text="✅ Готово (продолжить)", callback_data="ss:done")])
    if count > 0:
        rows.append([Btn(text="🔄 Начать заново", callback_data="ss:new")])
    rows.append([Btn(text="❌ Отмена", callback_data="ss:cancel")])
    return _kb(rows)


# ── Шаги конструктора ────────────────────────────────────────────────────────
def duration_kb() -> InlineKeyboardMarkup:
    btns = [Btn(text=f"{v} сек", callback_data=f"ss:dur:{v}") for v in config.DURATIONS]
    return _kb(_chunk(btns, 4) + [_nav(back=False)])


def interval_kb() -> InlineKeyboardMarkup:
    btns = [Btn(text=f"{v} сек", callback_data=f"ss:int:{v}") for v in config.INTERVALS]
    return _kb(_chunk(btns, 3) + [_nav(back=True)])


def ratio_kb() -> InlineKeyboardMarkup:
    btns = [Btn(text=t, callback_data=f"ss:ratio:{k}") for k, t in RATIO_BUTTONS.items()]
    return _kb(_chunk(btns, 2) + [_nav(back=True)])


def filter_kb() -> InlineKeyboardMarkup:
    btns = [Btn(text=t, callback_data=f"ss:flt:{k}") for k, t in FILTER_BUTTONS.items()]
    return _kb([btns, _nav(back=True)])


def brightness_kb() -> InlineKeyboardMarkup:
    btns = [Btn(text=f"{v}%", callback_data=f"ss:br:{v}") for v in config.BRIGHTNESS]
    return _kb(_chunk(btns, 3) + [_nav(back=True)])


# ── Подтверждение и результат ────────────────────────────────────────────────
def confirm_kb() -> InlineKeyboardMarkup:
    return _kb(
        [
            [Btn(text="🚀 Собрать видео", callback_data="ss:build")],
            [Btn(text="⚙️ Изменить настройки", callback_data="ss:edit")],
            [Btn(text="🔄 Загрузить новые фото", callback_data="ss:new")],
        ]
    )


def result_kb() -> InlineKeyboardMarkup:
    """Под готовым видео."""
    return _kb(
        [
            [Btn(text="🔄 Сделать еще вариант из этих фото", callback_data="ss:again")],
            [Btn(text="⚙️ Изменить настройки", callback_data="ss:edit")],
            [Btn(text="📁 Загрузить новые фото", callback_data="ss:new")],
        ]
    )
