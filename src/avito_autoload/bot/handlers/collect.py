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

QUESTION_COMPETITORS = (
    "\U0001F4CC Вопрос 3 из 8\n"
    "\n"
    "Отправь файл с объявлениями конкурентов (.xlsx), если он есть.\n"
    "\n"
    "Если файла нет \u2014 скопируй и вставь текст объявлений конкурентов вручную."
)

QUESTION_ADDRESSES = (
    "\U0001F4CC Вопрос 4 из 8\n"
    "\n"
    "Укажи адреса для объявлений (обязательный параметр).\n"
    "\n"
    "Свои адреса можно посмотреть здесь:\n"
    "https://www.avito.ru/profile/seller-address/goods?fromPage=distribution_page"
)

QUESTION_MANAGERS = (
    "\U0001F4CC Вопрос 5 из 8\n"
    "\n"
    "Укажи имя менеджера для каждого адреса.\n"
    "На каждом адресе должен быть свой уникальный менеджер "
    "(имена могут быть любыми).\n"
    "\n"
    "Пример:\n"
    "г. Москва, ул. Ленина, 10 \u2014 Алексей\n"
    "г. Казань, пр. Мира, 25 \u2014 Ольга\n"
    "г. Самара, ул. Советская, 3 \u2014 Дмитрий"
)

QUESTION_PHONE = (
    "\U0001F4CC Вопрос 6 из 8\n"
    "\n"
    "Укажи контактный номер телефона (обязательный параметр).\n"
    "\n"
    "Пример: +7 (999) 123-45-67"
)

QUESTION_COMPANY_INFO = (
    "\U0001F4CC Вопрос 7 из 8\n"
    "\n"
    "Расскажи коротко о своей компании:\n"
    "\u2022 Чем занимаетесь?\n"
    "\u2022 В чём ваше преимущество перед конкурентами?\n"
    "\u2022 Почему клиенты выбирают именно вас?\n"
    "\n"
    "Это поможет составить более продающие описания для объявлений."
)

QUESTION_TITLE_INFO = (
    "\U0001F4CC Вопрос 8 из 8\n"
    "\n"
    "Как формировать заголовки объявлений?\n"
    "\n"
    "Укажи, что важно добавлять в заголовок:\n"
    "\u2022 Применяемость (для какой техники/авто)\n"
    "\u2022 Бренд/производитель\n"
    "\u2022 Состояние (Новое, Б/У)\n"
    "\u2022 Выгода (гарантия, рассрочка, скидка)\n"
    "\n"
    "Примеры хороших заголовков:\n"
    "\u2022 Вал коленчатый Cummins С4934862 КамАЗ Евро-3/4\n"
    "\u2022 Двери межкомнатные, массив ольхи. Гарантия 5 лет\n"
    "\u2022 Арматура 12 мм А500С ГОСТ. Доставка в день заказа\n"
    "\n"
    "Напиши свои правила или пример заголовка.\n"
    "Если не уверен \u2014 напиши \u00abавто\u00bb, и я сам подберу формат."
)


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
        "\U0001F4CC Вопрос 2 из 8\n"
        "\n"
        "Отправь прайс-лист в формате Excel (.xlsx), если он есть.\n"
        "В файле должны быть обязательно: артикул, название, цена.\n"
        "\n"
        "Если прайс-листа нет \u2014 просто напиши список своих товаров или услуг текстом."
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
    await message.answer(QUESTION_COMPETITORS)


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
    await state.set_state(ProjectStates.waiting_addresses)
    await message.answer(QUESTION_ADDRESSES)


# Handle wrong input types — remind user what's expected

@router.message(ProjectStates.waiting_niche)
async def waiting_niche_wrong(message: Message) -> None:
    """User sent non-text (e.g. file) when niche text is expected."""
    await message.answer(
        "\u26a0\ufe0f Сначала напиши нишу текстом.\n"
        "Например: \u00abЗапчасти для грузовиков\u00bb, \u00abМежкомнатные двери\u00bb, "
        "\u00abЭлектроинструменты\u00bb"
    )


@router.message(ProjectStates.waiting_pricelist, F.text)
async def receive_pricelist_text(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive pricelist as text (list of products/services)."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, pricelist_text=text)
    await state.set_state(ProjectStates.waiting_competitors)

    await message.answer("\u2705 Список товаров/услуг получен")
    await message.answer(QUESTION_COMPETITORS)


@router.message(ProjectStates.waiting_competitors, F.text)
async def receive_competitors_text(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive competitors info as text."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, competitors_text=text)

    await message.answer("\u2705 Данные о конкурентах получены")
    await state.set_state(ProjectStates.waiting_addresses)
    await message.answer(QUESTION_ADDRESSES)


@router.message(ProjectStates.waiting_addresses, F.text)
async def receive_addresses(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive seller addresses."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, addresses=text)

    await message.answer("\u2705 Адреса сохранены")
    await state.set_state(ProjectStates.waiting_managers)
    await message.answer(QUESTION_MANAGERS)


@router.message(ProjectStates.waiting_addresses)
async def waiting_addresses_wrong(message: Message) -> None:
    """Remind user to send addresses as text."""
    await message.answer(
        "\u26a0\ufe0f Напиши адреса текстом.\n"
        "Посмотреть свои адреса можно здесь:\n"
        "https://www.avito.ru/profile/seller-address/goods?fromPage=distribution_page"
    )


@router.message(ProjectStates.waiting_managers, F.text)
async def receive_managers(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive manager names per address."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, managers=text)

    await message.answer("\u2705 Менеджеры сохранены")
    await state.set_state(ProjectStates.waiting_phone)
    await message.answer(QUESTION_PHONE)


@router.message(ProjectStates.waiting_managers)
async def waiting_managers_wrong(message: Message) -> None:
    """Remind user to send manager names as text."""
    await message.answer(
        "\u26a0\ufe0f Напиши имена менеджеров текстом.\n"
        "\n"
        "Пример:\n"
        "г. Москва, ул. Ленина, 10 \u2014 Алексей\n"
        "г. Казань, пр. Мира, 25 \u2014 Ольга"
    )


@router.message(ProjectStates.waiting_phone, F.text)
async def receive_phone(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive contact phone number."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, phone=text)

    await message.answer(f"\u2705 Телефон сохранён: {text}")
    await state.set_state(ProjectStates.waiting_company_info)
    await message.answer(QUESTION_COMPANY_INFO)


@router.message(ProjectStates.waiting_phone)
async def waiting_phone_wrong(message: Message) -> None:
    """Remind user to send phone as text."""
    await message.answer(
        "\u26a0\ufe0f Напиши номер телефона текстом.\n"
        "\n"
        "Пример: +7 (999) 123-45-67"
    )


@router.message(ProjectStates.waiting_company_info, F.text)
async def receive_company_info(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive company description and USP."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, company_info=text)

    await message.answer("\u2705 Информация о компании сохранена")
    await state.set_state(ProjectStates.waiting_title_info)
    await message.answer(QUESTION_TITLE_INFO)


@router.message(ProjectStates.waiting_company_info)
async def waiting_company_info_wrong(message: Message) -> None:
    """Remind user to send company info as text."""
    await message.answer(
        "\u26a0\ufe0f Напиши описание компании текстом.\n"
        "\n"
        "Расскажи, чем занимаетесь и в чём ваши преимущества."
    )


@router.message(ProjectStates.waiting_title_info, F.text)
async def receive_title_info(
    message: Message,
    state: FSMContext,
    db: ProjectDB,
) -> None:
    """Receive title format preferences."""
    text = message.text.strip()
    data = await state.get_data()
    project_id = data["project_id"]

    await db.update_project(project_id, title_info=text)

    await message.answer("\u2705 Правила заголовков сохранены")
    await message.answer("Все данные получены! Составляю план работы...")

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


@router.message(ProjectStates.waiting_title_info)
async def waiting_title_info_wrong(message: Message) -> None:
    """Remind user to send title info as text."""
    await message.answer(
        "\u26a0\ufe0f Напиши правила заголовков текстом.\n"
        "\n"
        "Или напиши \u00abавто\u00bb, чтобы я подобрал формат сам."
    )
