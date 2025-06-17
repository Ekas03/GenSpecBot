from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram import Dispatcher

def fallback_message(dp: Dispatcher):
    @dp.message(StateFilter(None))
    async def fallback(message: Message):
        if message.text and message.text.startswith("/"):
            return
        await message.answer(f"Не знаю, что это значит :( \n\n"
                             f"Чтобы отправить интервью на анализ, используй команду\n\n/new_interview\n\n")

