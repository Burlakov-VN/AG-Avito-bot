"""Handlers for data collection: niche, pricelist, competitors."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from avito_autoload.bot.keyboards import start_plan_keyboard
from avito_autoload.bot.states import ProjectStates
from avito_autoload.bot.storage.database import ProjectDB
from avito_autoload.bot.storage.files import FileStorage

logger = logging.getLogger(__name__)

router = Router()


@router.message(ProjectStates.waiting_niche, F.text)
async def receive_niche(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive niche text from user."""
    niche = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, niche=niche)
    await state.set_state(ProjectStates.waiting_pricelist)

    await message.answer(f"\u2705 Ниша: \u00ab{niche}\u00bb")
    await message.answer(
        "\U0001F4CC Вопрос 2 из 3\n"
        "\n"
        "Отправь прайс-лист в формате Excel (.xlsx).\n"
        "В файле должны быть: код, артикул, название, цена."
    )


@router.message(ProjectStates.waiting_pricelist, F.document)
async def receive_pricelist(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: ProjectDB,
    file_storage: FileStorage,
) -> None:
    """Receive pricelist file."""
    doc = message.document
    if not doc.file_name or not doc.file_name.endswith(".xlsx"):
        await message.answer(
            "\u26a0\ufe0f Мне нужен файл в формате Excel (.xlsx). Попробуй ещё раз."
        )
        return

    data = await state.get_data()
    project_id = data["project_id"]

    # Download file
    file_path = await file_storage.download_file(
        bot, doc.file_id, message.from_user.id, project_id, doc.file_name,
    )
    await db.update_project(project_id, pricelist_path=str(file_path))

    # Count rows for user feedback
    try:
        from avito_autoload.parsers.xlsx_parser import parse_xlsx
        rows = parse_xlsx(file_path)
        count = len(rows)
    except Exception:
        count = 0
        logger.exception("Failed to parse pricelist for row count")

    await state.set_state(ProjectStates.waiting_competitors)

    count_text = f" ({count} позиций)" if count else ""
    await message.answer(f"\u2705 Прайс-лист получен: {doc.file_name}{count_text}")
    await message.answer(
        "\U0001F4CC Вопрос 3 из 3\n"
        "\n"
        "Отправь файл с объявлениями конкурентов (.xlsx).\n"
        "Это выгрузка из Авито \u2014 можно скачать в разделе аналитики."
    )


@router.message(ProjectStates.waiting_competitors, F.document)
async def receive_competitors(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: ProjectDB,
    file_storage: FileStorage,
) -> None:
    """Receive competitors file."""
    doc = message.document
    if not doc.file_name or not doc.file_name.endswith(".xlsx"):
        await message.answer(
            "\u26a0\ufe0f Мне нужен файл в формате Excel (.xlsx). Попробуй ещё раз."
        )
        return

    data = await state.get_data()
    project_id = data["project_id"]

    # Download file
    file_path = await file_storage.download_file(
        bot, doc.file_id, message.from_user.id, project_id, "competitors_" + doc.file_name,
    )
    await db.update_project(project_id, competitors_path=str(file_path))

    # Count competitor ads
    try:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True)
        ws = wb.active
        count = max(ws.max_row - 1, 0) if ws.max_row else 0
        wb.close()
    except Exception:
        count = 0
        logger.exception("Failed to count competitor ads")

    count_text = f" ({count} объявлений)" if count else ""

    await message.answer(f"\u2705 Конкуренты: {doc.file_name}{count_text}")
    await message.answer("Все данные получены! Составляю план работы...")

    # Show the plan
    await state.set_state(ProjectStates.confirming_plan)
    await message.answer(
        "\U0001F4CB План работы готов!\n"
        "\n"
        "Я проведу 4 этапа:\n"
        "\n"
        "1\ufe0f\u20e3 Анализ целевой аудитории\n"
        "   Изучу нишу, определю сегменты покупателей, их боли и мотивацию\n"
        "\n"
        "2\ufe0f\u20e3 Подготовка шаблона описаний\n"
        "   На основе анализа ЦА и конкурентов создам шаблон продающего текста\n"
        "\n"
        "3\ufe0f\u20e3 Категоризация товаров\n"
        "   Определю категории и подкатегории Авито для каждого товара\n"
        "\n"
        "4\ufe0f\u20e3 Сборка файла автозагрузки\n"
        "   Сгенерирую описания и соберу готовый файл\n"
        "\n"
        "После каждого этапа покажу результат \u2014 ты сможешь подтвердить или внести правки.\n"
        "\n"
        "Начинаем?",
        reply_markup=start_plan_keyboard(),
    )


# Handle wrong input types — remind user what's expected

@router.message(ProjectStates.waiting_niche)
async def waiting_niche_wrong(message: Message) -> None:
    """User sent non-text (e.g. file) when niche text is expected."""
    await message.answer(
        "\u26a0\ufe0f Сначала напиши нишу текстом.\n"
        "Например: \u00abЗапчасти для грузовиков\u00bb, \u00abМежкомнатные двери\u00bb, "
        "\u00abЭлектроинструменты\u00bb"
    )


@router.message(ProjectStates.waiting_pricelist)
async def waiting_pricelist_text(message: Message) -> None:
    """Remind user to send a file."""
    await message.answer(
        "\u26a0\ufe0f Мне нужен файл в формате Excel (.xlsx). Отправь прайс-лист как документ."
    )


@router.message(ProjectStates.waiting_competitors)
async def waiting_competitors_text(message: Message) -> None:
    """Remind user to send a file."""
    await message.answer(
        "\u26a0\ufe0f Мне нужен файл в формате Excel (.xlsx). Отправь файл конкурентов как документ."
    )
