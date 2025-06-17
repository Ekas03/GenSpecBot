import re
import pymorphy2
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Document
from docx import Document as DocxDocument
from tempfile import NamedTemporaryFile
from fsm import InterviewStates
from transformers import pipeline

morph = pymorphy2.MorphAnalyzer()

# первое лицо во множественном числе (мы, наш)
FIRST_PERSON_PLURAL_LEMMAS = {"мы", "наш"}

# первое лицо в единственном числе (я, мой)
FIRST_PERSON_SINGULAR_LEMMAS = {"я", "мой"}

# суффиксы, характерные для отглагольных существительных
DEVERBAL_SUFFIXES = ("ние", "ция", "тельство", "ание", "ение", "ка")

# нормальная форма слова
def get_lemma(word: str) -> str:
    return morph.parse(word)[0].normal_form

# похоже ли на отглагольное
def looks_like_deverbal(noun: str) -> bool:
    return noun.endswith(DEVERBAL_SUFFIXES)

# подсчет ОБЩИХ признаков
def contains_label0_features(sentence: str) -> int:
    words = sentence.lower().split()
    counter = 0
    for word in words:
        parsed = morph.parse(word)[0]
        lemma = parsed.normal_form
        tag = parsed.tag

        # местоимение 1-го лица множественного числа
        if lemma in FIRST_PERSON_PLURAL_LEMMAS:
            counter += 1

        # глагол 1-го лица множественного числа
        if ("VERB" in tag or "INFN" in tag) and "1per" in tag and "plur" in tag:
            counter += 1

        # глагол совершенного вида
        if ("VERB" in tag or "INFN" in tag) and "perf" in tag:
            counter += 1

        # пассивная форма
        if "pssv" in tag:
            counter += 1

        # причастие или деепричастие
        if "PRTF" in tag or "GRND" in tag:
            counter += 1

    return counter

# подсчет ЧАСТНЫХ признаков
def contains_label1_features(sentence: str) -> int:
    words = sentence.lower().split()
    parsed_words = [(w, morph.parse(w)[0]) for w in words]
    counter = 0

    for w, p in parsed_words:
        lemma = p.normal_form
        tag = p.tag

        # местоимение 1-го лица единственного числа
        if lemma in FIRST_PERSON_SINGULAR_LEMMAS:
            counter += 1

        # глагол 1-го лица единственного числа
        if ("VERB" in tag or "INFN" in tag) and "1per" in tag and "sing" in tag:
            counter += 1

    # отглагольное существительное
    if any("NOUN" in p.tag and looks_like_deverbal(w) for w, p in parsed_words):
        counter += 1

    # глаголы несовершенного вида
    if any(("VERB" in p.tag or "INFN" in p.tag) and "impf" in p.tag for w, p in parsed_words):
        counter += 1

    # три и более глагола подряд
    tokens = re.split(r"[,\s]+", sentence.lower())
    run = 0
    for t in tokens:
        p = morph.parse(t)[0]
        if "VERB" in p.tag or "INFN" in p.tag:
            run += 1
            if run >= 3:
                counter += 1
        else:
            run = 0

    return counter

analyzer_pipeline = pipeline("text-classification", model="ekas03/my_genspec_analyzer")

def split_into_sentences(text: str):
    return re.split(r'(?<=[.!?])\s+', text.strip())

def new_interview(dp: Dispatcher):
    @dp.message(F.text == "/new_interview")
    async def message_interview(message: Message, state: FSMContext):
        await message.answer(
            "Отправь файл в формате .DOCX с интервью, где вопросы должны начинаться с \"В:\", а ответы с \"О:\""
        )
        await state.set_state(InterviewStates.waiting_for_docx)

    @dp.message(InterviewStates.waiting_for_docx, F.document)
    async def handle_docx(message: Message, state: FSMContext):
        doc: Document = message.document

        if not doc.file_name.lower().endswith(".docx"):
            await message.answer("ОШИБКА: нужен файл в формате .DOCX с интервью, где вопросы должны начинаться с \"В:\", а ответы с \"О:\"! Отправь новое интервью:")
            return

        try:
            file = await message.bot.get_file(doc.file_id)
            file_bytes = await message.bot.download_file(file.file_path)

            with NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(file_bytes.read())
                tmp_path = tmp.name

            parsed = DocxDocument(tmp_path)
            lines = [p.text.strip() for p in parsed.paragraphs if p.text.strip()]
            valid = all(line.startswith("В:") or line.startswith("О:") for line in lines)

            if not valid:
                await message.answer(
                    "ОШИБКА: неверная структура интервью!\n"
                    "Необходимо, чтобы вопросы начинались с \"В:\", а ответы с \"О:\".\n"
                    "Отправь новое интервью:"
                )
                return

            sentences = []
            for line in lines:
                if line.startswith("О:"):
                    content = line[2:].strip()
                    sentences.extend(split_into_sentences(content))

            if not sentences:
                await message.answer("ОШИБКА: ответов (начинаются с \"О:\") не найдены! Попробуй снова /new_interview")
                return

            counts_model = {"LABEL_0": 0, "LABEL_1": 0}
            counts_morph = {"LABEL_0": 0, "LABEL_1": 0}

            for sent in sentences:
                model_result = analyzer_pipeline(sent, truncation=True)[0]
                counts_model[model_result["label"]] += 1

                score0 = contains_label0_features(sent)
                score1 = contains_label1_features(sent)
                morph_label = "LABEL_0" if score0 > score1 else "LABEL_1"
                counts_morph[morph_label] += 1

            classification_model = "ОБЩЕЕ" if counts_model["LABEL_0"] > counts_model["LABEL_1"] else "ЧАСТНОЕ"
            classification_morph = "ОБЩЕЕ" if counts_morph["LABEL_0"] > counts_morph["LABEL_1"] else "ЧАСТНОЕ"

            await message.answer(
                "📊 Интервью проанализировано:\n\n"
                f"<b>Анализ языковой модели</b>:\n"
                f"ОБЩИХ признаков: {counts_model['LABEL_0']}\n"
                f"ЧАСТНЫХ признаков: {counts_model['LABEL_1']}\n"
                f"<b>Результат:</b> {classification_model}\n\n"
                f"<b>Морфологический анализ</b>:\n"
                f"ОБЩИХ признаков: {counts_morph['LABEL_0']}\n"
                f"ЧАСТНЫХ признаков: {counts_morph['LABEL_1']}\n"
                f"<b>Результат:</b> {classification_morph}"
            )
            await state.clear()

        except Exception as e:
            print(f"[Analyzer error] {e}")
            await message.answer("Проихошла ошибка, попробуй снова /new_interview")
