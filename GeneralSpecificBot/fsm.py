from aiogram.fsm.state import StatesGroup, State


class InterviewStates(StatesGroup):
    waiting_for_docx = State()