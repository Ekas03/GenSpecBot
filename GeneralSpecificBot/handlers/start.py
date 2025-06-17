from aiogram import F, Dispatcher
from aiogram.types import Message

# стартовый обработчик команды /start
def start_handlers(dp: Dispatcher):
    @dp.message(F.text == "/start")
    async def cmd_start(message: Message):
        await message.answer(f"Привет, {message.from_user.first_name}! \n\n"
                             f"👋 Добро пожаловать в чат-бот \"ОБЩЕЕ-ЧАСТНОЕ\"!\n\n"
                             f"Чтобы отправить интервью на анализ, используй команду\n\n/new_interview\n\n"
                             f"Помни, что интервью должно быть в формате DOCX-файла, где вопрос начинается с \"В:\", а ответ с \"О:\"")