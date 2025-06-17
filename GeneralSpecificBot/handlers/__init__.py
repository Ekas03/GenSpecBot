from aiogram import Dispatcher
from handlers.fallback import fallback_message
from handlers.new_interview import new_interview
from handlers.start import start_handlers


def register_all_handlers(dp: Dispatcher):
    start_handlers(dp)
    new_interview(dp)
    fallback_message(dp)