import asyncio
import contextlib
import logging
import os
import shutil

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from handlers import fallback, slideshow, start
from middlewares.subscription import SubscriptionMiddleware
from services.jobs import purge_temp
from services.storage import purge_stale

STALE_AFTER = 6 * 3600  # сек: папки брошенных пользователей чистим через 6 часов
PORT = int(os.getenv("PORT", "10000"))  # Render передаёт порт через PORT


# ── Мини HTTP-сервер для Render ──────────────────────────────────────────────
async def handle_root(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "bot": "running"})


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", handle_root)  # GET "/" (HEAD aiohttp добавляет сам)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)  # 0.0.0.0 обязателен на Render
    await site.start()  # не блокирует — сервер работает в фоне этого же event loop
    logging.info("HTTP server listening on 0.0.0.0:%d", PORT)
    return runner


# ── Фоновая чистка temp ──────────────────────────────────────────────────────
async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(1800)
        removed = await asyncio.to_thread(purge_stale, STALE_AFTER)
        if removed:
            logging.info("Удалено устаревших папок temp: %d", removed)


# ── Запуск ───────────────────────────────────────────────────────────────────
async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.BOT_TOKEN or config.BOT_TOKEN.startswith("PASTE_"):
        raise SystemExit("Укажите токен бота: BOT_TOKEN в config.py или в переменных окружения")
    if shutil.which(config.FFMPEG_BIN) is None:
        raise SystemExit(f"ffmpeg не найден ('{config.FFMPEG_BIN}')")

    purge_temp()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    sub = SubscriptionMiddleware()
    dp.message.outer_middleware(sub)
    dp.callback_query.outer_middleware(sub)
    dp.include_routers(start.router, slideshow.router, fallback.router)  # fallback — последний

    # Сначала веб-сервер: Render должен сразу увидеть открытый порт
    runner = await start_web_server()
    cleaner = asyncio.create_task(cleanup_loop())

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started")
    try:
        await dp.start_polling(bot)  # блокирует только эту корутину, веб-сервер продолжает отвечать
    finally:
        cleaner.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleaner
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass