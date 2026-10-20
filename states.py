from aiogram.fsm.state import State, StatesGroup


class SlideShow(StatesGroup):
    photos = State()
    duration = State()
    interval = State()
    ratio = State()
    filter = State()
    brightness = State()
    confirm = State()
