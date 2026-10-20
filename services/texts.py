"""Тексты сводки и подписи к видео (без зависимостей от aiogram)."""
from __future__ import annotations

RATIO_SHORT = {"9x16": "9:16", "16x9": "16:9", "1x1": "1:1", "4x5": "4:5"}
FILTER_TITLES = {"none": "Без фильтра", "bw": "Чёрно-белый (B&W)"}


def summary_text(d: dict) -> str:
    return (
        "📋 <b>Всё готово к сборке:</b>\n"
        f"- Фото: {len(d['photos'])}\n"
        f"- Длина: {d['duration']} сек\n"
        f"- Смена фото: каждые {d['interval']} сек\n"
        f"- Формат: {RATIO_SHORT[d['ratio']]}\n"
        f"- Фильтр: {FILTER_TITLES[d['filter']]}\n"
        f"- Яркость: {d['brightness']}%"
    )


def result_caption(d: dict) -> str:
    return (
        "✅ <b>Готово!</b>\n"
        f"Параметры: {len(d['photos'])} фото | {d['duration']}с | Смена {d['interval']}с | "
        f"{RATIO_SHORT[d['ratio']]} | {FILTER_TITLES[d['filter']]} | {d['brightness']}%"
    )
