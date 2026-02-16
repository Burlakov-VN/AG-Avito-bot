"""Handlers for /start, /help, /cancel commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from avito_autoload.bot.states import ProjectStates
from avito_autoload.bot.storage.database import ProjectDB

router = Router()

WELCOME_TEXT = (
    "\U0001F44B Привет! Я помогу подготовить файл автозагрузки для Авито.\n"
    "\n"
    "Мне нужно задать тебе несколько вопросов, а потом попрошу загрузить файлы."
)

QUESTION_NICHE = (
    "\U0001F4CC Вопрос 1 из 7\n"
    "\n"
    "Подскажи свою нишу на Авито?\n"
    "\n"
    "Например: \u00abЗапчасти для грузовиков\u00bb, \u00abМежкомнатные двери\u00bb, "
    "\u00abЭлектроинструменты\u00bb"
)

HELP_TEXT = (
    "🤖 @uv_avito_bot — бот для подготовки автозагрузки Авито\n"
    "\n"
    "Команды:\n"
    "/start — начать новый проект\n"
    "/status — текущий статус\n"
    "/cancel — отменить текущую задачу"
)

CANCEL_TEXT = "❌ Текущая задача отменена. Чтобы начать заново — /start"


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: ProjectDB) -> None:
    """Handle /start command."""
    await state.clear()

    # Create a new project in DB
    project_id = await db.create_project(message.from_user.id)
    await state.update_data(project_id=project_id)

    await state.set_state(ProjectStates.waiting_niche)
    await message.answer(WELCOME_TEXT)
    await message.answer(QUESTION_NICHE)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command."""
    await state.clear()
    await message.answer(CANCEL_TEXT)


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext, db: ProjectDB) -> None:
    """Handle /status command."""
    project = await db.get_active_project(message.from_user.id)
    if project is None:
        await message.answer("Нет активного проекта. Нажми /start для начала.")
        return

    current = await state.get_state()
    state_labels = {
        ProjectStates.waiting_niche.state: "Ожидание ниши",
        ProjectStates.waiting_pricelist.state: "Ожидание прайс-листа",
        ProjectStates.waiting_competitors.state: "Ожидание файла конкурентов",
        ProjectStates.waiting_addresses.state: "Ожидание адресов",
        ProjectStates.waiting_managers.state: "Ожидание менеджеров",
        ProjectStates.waiting_phone.state: "Ожидание телефона",
        ProjectStates.waiting_company_info.state: "Ожидание описания компании",
        ProjectStates.confirming_plan.state: "План готов, ожидание подтверждения",
        ProjectStates.running_ca_analysis.state: "Анализ ЦА...",
        ProjectStates.confirming_ca.state: "Анализ ЦА готов",
        ProjectStates.running_template.state: "Подготовка шаблона...",
        ProjectStates.confirming_template.state: "Шаблон готов",
        ProjectStates.running_categories.state: "Категоризация...",
        ProjectStates.confirming_categories.state: "Категории готовы",
        ProjectStates.running_pipeline.state: "Сборка файла...",
        ProjectStates.complete.state: "Готово!",
    }
    label = state_labels.get(current, current or "Не активен")
    niche = project.get("niche") or "—"
    await message.answer(
        f"📊 Проект #{project['id']}\n"
        f"Ниша: {niche}\n"
        f"Статус: {label}"
    )
