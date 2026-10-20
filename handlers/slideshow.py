"""Слайд-шоу: приём 2–5 фото → 5 шагов → подтверждение → сборка.

Фото сохраняются в temp/{user_id}/photos/ (пути — в FSM) и живут, пока пользователь не загрузит новые
или не отменит. Рабочие файлы сборки — в temp/{user_id}/jobs/{id}/, удаляются сразу после отправки.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from handlers.common import edit_or_send, image_ref, reset_user, send_video
from handlers.start import WELCOME_TEXT
from keyboards import inline as kb
from middlewares.album import AlbumMiddleware
from services.ffmpeg_builder import RATIOS, FFmpegError, SlideshowSettings, build_slideshow
from services.jobs import JobBusy, user_job
from services.storage import clear_photos, save_photos
from services.texts import result_caption, summary_text
from states import SlideShow

log = logging.getLogger(__name__)
router = Router()
router.message.middleware(AlbumMiddleware())
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

MIN_P, MAX_P = config.MIN_PHOTOS, config.MAX_PHOTOS
IMAGE = F.photo | F.document.mime_type.startswith("image/")

PHOTOS_TEXT = (
    f"📸 <b>Загрузка фото</b>\n\nОтправьте от {MIN_P} до {MAX_P} фото — одним альбомом или по одному. "
    "Лучшее качество — отправлять как файл."
)

STEP_ORDER = [
    SlideShow.duration, SlideShow.interval, SlideShow.ratio,
    SlideShow.filter, SlideShow.brightness, SlideShow.confirm,
]


def _view(step: State, d: dict) -> tuple[str, InlineKeyboardMarkup]:
    if step == SlideShow.duration:
        return "⏱ <b>Шаг 1 из 5: Длина видео</b>\n\nОбщий хронометраж ролика:", kb.duration_kb()
    if step == SlideShow.interval:
        return ("🎞 <b>Шаг 2 из 5: Скорость смены кадров</b>\n\n"
                "Через сколько секунд меняется фото (фото зацикливаются до конца видео):"), kb.interval_kb()
    if step == SlideShow.ratio:
        return ("📐 <b>Шаг 3 из 5: Формат кадра</b>\n\n"
                "📱 9:16 — вертикаль (TikTok, Reels, Shorts)\n"
                "💻 16:9 — горизонталь, полоса из центра фото\n"
                "⏹ 1:1 — квадрат\n"
                "📸 4:5 — пост"), kb.ratio_kb()
    if step == SlideShow.filter:
        return "🎨 <b>Шаг 4 из 5: Фильтр</b>", kb.filter_kb()
    if step == SlideShow.brightness:
        return "💡 <b>Шаг 5 из 5: Яркость кадра</b>\n\n100% — как есть, 10% — очень тёмный кадр:", kb.brightness_kb()
    return summary_text(d), kb.confirm_kb()


async def show_step(
    state: FSMContext, step: State, *, call: CallbackQuery | None = None, message: Message | None = None
) -> None:
    await state.set_state(step)
    text, markup = _view(step, await state.get_data())
    if call:
        await edit_or_send(call, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


# ── Вход / сброс / отмена ────────────────────────────────────────────────────
@router.callback_query(F.data == "ss:new")
async def new_photos(call: CallbackQuery, state: FSMContext) -> None:
    """Из любого места: старые фото удаляются, бот ждёт новый пак."""
    await call.answer()
    await reset_user(state, call.from_user.id)
    await state.set_state(SlideShow.photos)
    await edit_or_send(call, PHOTOS_TEXT, kb.photos_kb(0))


@router.callback_query(StateFilter(SlideShow.photos, *STEP_ORDER), F.data == "ss:cancel")
async def cancel(call: CallbackQuery, state: FSMContext) -> None:
    await reset_user(state, call.from_user.id)  # отмена = чистим temp/{user_id}/
    await call.answer("Отменено")
    await edit_or_send(call, WELCOME_TEXT, kb.welcome_kb())


# ── Приём фото ───────────────────────────────────────────────────────────────
async def _save_to_state(
    bot: Bot, message: Message, state: FSMContext, album: list[Message] | None
) -> tuple[list[str], str]:
    """Возвращает (пути фото, статус): album | single | full | too_many.
    Альбом заменяет предыдущий набор; одиночное фото дописывается (максимум MAX_P)."""
    uid = message.from_user.id
    refs = [r for m in (album or [message]) if (r := image_ref(m))]
    async with _locks[uid]:
        if len(refs) > 1:  # альбом
            await clear_photos(uid)
            if len(refs) > MAX_P:
                await state.update_data(photos=[])
                return [], "too_many"
            paths = await save_photos(bot, uid, refs)
            photos = [str(p) for p in paths]
            await state.update_data(photos=photos)
            return photos, "album"

        data = await state.get_data()
        existing = [p for p in data.get("photos", []) if Path(p).exists()]
        if len(existing) >= MAX_P:
            return existing, "full"
        paths = await save_photos(bot, uid, refs[:1])
        photos = existing + [str(p) for p in paths]
        await state.update_data(photos=photos)
        return photos, "single"


@router.message(StateFilter(SlideShow.photos, None), IMAGE)
async def got_photos(
    message: Message, state: FSMContext, bot: Bot, album: list[Message] | None = None
) -> None:
    if await state.get_state() is None:  # фото прислали сразу, без кнопки
        await state.set_state(SlideShow.photos)
    try:
        photos, status = await _save_to_state(bot, message, state, album)
    except Exception:
        log.exception("photo download failed")
        await message.answer("❌ Не удалось загрузить фото. Попробуйте отправить ещё раз.")
        return

    n = len(photos)
    if status == "too_many":
        await message.answer(
            f"⚠️ В альбоме больше {MAX_P} фото. Отправьте от {MIN_P} до {MAX_P} фото заново.",
            reply_markup=kb.photos_kb(0),
        )
    elif status == "album":
        await message.answer(f"📥 Загружено фото: <b>{n}</b>")
        await show_step(state, SlideShow.duration, message=message)
    elif status == "full":
        await message.answer(
            f"⚠️ Уже загружено {n}/{MAX_P} — это максимум. Нажмите «Готово» или начните заново.",
            reply_markup=kb.photos_kb(n),
        )
    elif n < MIN_P:
        await message.answer(
            f"📥 Загружено фото: <b>{n}/{MAX_P}</b>\nНужно минимум {MIN_P} — отправьте ещё.",
            reply_markup=kb.photos_kb(n),
        )
    else:
        await message.answer(f"📥 Загружено фото: <b>{n}/{MAX_P}</b>", reply_markup=kb.photos_kb(n))


@router.callback_query(SlideShow.photos, F.data == "ss:done")
async def photos_done(call: CallbackQuery, state: FSMContext) -> None:
    photos = [p for p in (await state.get_data()).get("photos", []) if Path(p).exists()]
    if not MIN_P <= len(photos) <= MAX_P:
        await call.answer(f"Нужно от {MIN_P} до {MAX_P} фото (сейчас {len(photos)})", show_alert=True)
        return
    await call.answer()
    await show_step(state, SlideShow.duration, call=call)


# ── Шаги конструктора ────────────────────────────────────────────────────────
@router.callback_query(SlideShow.duration, F.data.startswith("ss:dur:"))
async def set_duration(call: CallbackQuery, state: FSMContext) -> None:
    v = int(call.data.split(":")[2])
    if v not in config.DURATIONS:
        return await call.answer()
    await state.update_data(duration=v)
    await call.answer()
    await show_step(state, SlideShow.interval, call=call)


@router.callback_query(SlideShow.interval, F.data.startswith("ss:int:"))
async def set_interval(call: CallbackQuery, state: FSMContext) -> None:
    v = float(call.data.split(":")[2])
    if v not in config.INTERVALS:
        return await call.answer()
    await state.update_data(interval=v)
    await call.answer()
    await show_step(state, SlideShow.ratio, call=call)


@router.callback_query(SlideShow.ratio, F.data.startswith("ss:ratio:"))
async def set_ratio(call: CallbackQuery, state: FSMContext) -> None:
    v = call.data.split(":")[2]
    if v not in RATIOS:
        return await call.answer()
    await state.update_data(ratio=v)
    await call.answer()
    await show_step(state, SlideShow.filter, call=call)


@router.callback_query(SlideShow.filter, F.data.startswith("ss:flt:"))
async def set_filter(call: CallbackQuery, state: FSMContext) -> None:
    v = call.data.split(":")[2]
    if v not in kb.FILTER_BUTTONS:
        return await call.answer()
    await state.update_data(filter=v)
    await call.answer()
    await show_step(state, SlideShow.brightness, call=call)


@router.callback_query(SlideShow.brightness, F.data.startswith("ss:br:"))
async def set_brightness(call: CallbackQuery, state: FSMContext) -> None:
    v = int(call.data.split(":")[2])
    if v not in config.BRIGHTNESS:
        return await call.answer()
    await state.update_data(brightness=v)
    await call.answer()
    await show_step(state, SlideShow.confirm, call=call)


@router.callback_query(StateFilter(*STEP_ORDER), F.data == "ss:back")
async def go_back(call: CallbackQuery, state: FSMContext) -> None:
    idx = [s.state for s in STEP_ORDER].index(await state.get_state())
    await call.answer()
    await show_step(state, STEP_ORDER[max(idx - 1, 0)], call=call)


# ── Экран подтверждения и кнопки под видео ───────────────────────────────────
@router.callback_query(SlideShow.confirm, F.data == "ss:edit")
async def edit_settings(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await show_step(state, SlideShow.duration, call=call)  # с шага 1, фото остаются


@router.callback_query(SlideShow.confirm, F.data == "ss:again")
async def another_variant(call: CallbackQuery, state: FSMContext) -> None:
    """«Ещё вариант из этих фото» → экран настроек с текущими параметрами и фото."""
    await call.answer()
    await show_step(state, SlideShow.confirm, call=call)


# ── Сборка ───────────────────────────────────────────────────────────────────
@router.callback_query(SlideShow.confirm, F.data == "ss:build")
async def build(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    d = await state.get_data()
    chat_id = call.message.chat.id
    sources = [Path(p) for p in d.get("photos", [])]
    if len(sources) < MIN_P or not all(p.exists() for p in sources):
        await call.answer("Сохранённые фото устарели — загрузите их заново", show_alert=True)
        await reset_user(state, call.from_user.id)
        await state.set_state(SlideShow.photos)
        await edit_or_send(call, PHOTOS_TEXT, kb.photos_kb(0))
        return

    s = SlideshowSettings(
        duration=d["duration"], interval=d["interval"], ratio=d["ratio"],
        filter=d["filter"], brightness=d["brightness"],
    )
    status: Message | None = None
    ok = False
    try:
        async with user_job(call.from_user.id) as job:
            await call.answer()
            status = await bot.send_message(chat_id, "⏳ Собираю видео...")
            out = await build_slideshow(sources, s, job)
            w, h = RATIOS[s.ratio]
            await send_video(
                bot, chat_id, out, width=w, height=h, duration=s.duration,
                caption=result_caption(d), reply_markup=kb.result_kb(),
            )
            ok = True
    except JobBusy:
        await call.answer("⏳ Предыдущая сборка ещё идёт — дождитесь результата", show_alert=True)
        return
    except FFmpegError:
        await bot.send_message(chat_id, "❌ Не удалось собрать видео. Попробуйте другие фото или настройки.")
    except Exception:
        log.exception("slideshow build failed")
        await bot.send_message(chat_id, "❌ Ошибка при сборке. Попробуйте ещё раз.")
    finally:
        if status:
            try:
                await status.delete()
            except TelegramAPIError:
                pass

    if not ok:  # при ошибке возвращаем экран подтверждения, чтобы можно было повторить
        await bot.send_message(chat_id, summary_text(d), reply_markup=kb.confirm_kb())
