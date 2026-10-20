# Slideshow Bot (aiogram 3 + ffmpeg)

Бот делает быстрые слайд-шоу из 2–5 фото. Больше ничего.

## Структура
```
main.py                     запуск, роутеры, middleware, фоновая чистка temp
config.py                   ТОКЕН, СПОНСОРЫ (ОП), опции конструктора
states.py                   FSM-состояния
handlers/                   start (приветствие, проверка ОП), slideshow (весь флоу), fallback, common
keyboards/inline.py         инлайн-клавиатуры
middlewares/                subscription (ОП), album (сборка медиагрупп)
services/ffmpeg_builder.py  сборка слайд-шоу (asyncio.subprocess + семафор)
services/jobs.py            temp/{user_id}/jobs/{id}/ — рабочие файлы одной сборки, автоудаление
services/storage.py         temp/{user_id}/photos/ — исходные фото, чистка брошенных папок
services/subscription.py    проверка подписки через getChatMember
services/texts.py           сводка и подпись к видео
```

## Запуск
1. Python 3.10+, ffmpeg в PATH (`ffmpeg -version`).
2. `pip install -r requirements.txt`
3. Токен: вставить в `config.py` (`BOT_TOKEN`) или `cp .env.example .env` и заполнить.
4. Спонсоры: заполнить `SPONSORS` в `config.py`. **Бот должен быть админом в каждом канале**, иначе
   Telegram не даст проверить подписку (тогда бот пропускает пользователя и пишет warning в лог).
5. `python main.py`

## Временные файлы
- `temp/{user_id}/photos/` — фото пользователя; живут между сборками, удаляются при «Загрузить новые фото»,
  «Отмена», /start.
- `temp/{user_id}/jobs/{id}/` — кадры и mp4 одной сборки; удаляются сразу после отправки.
- Брошенные папки (старше 6 часов) чистятся фоном; при старте бота `temp/` очищается целиком.

## Заметки
- Лимит скачивания файлов ботом — 20 МБ, отправки — 50 МБ.
- FSM хранится в памяти (после рестарта шаги сбрасываются). Для продакшена — RedisStorage.
