"""Handlers for inline keyboard callbacks."""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from avito_autoload.bot.states import ProjectStates
from avito_autoload.bot.storage.database import ProjectDB
from avito_autoload.bot.storage.files import FileStorage

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "plan_start")
async def on_plan_start(
    callback: CallbackQuery, state: FSMContext, db: ProjectDB,
) -> None:
    """User pressed 'Start' on plan screen."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    # Transition to CA analysis — the analysis handler will pick this up
    await state.set_state(ProjectStates.running_ca_analysis)

    await callback.message.answer(
        "\u23f3 Этап 1/4: Анализ целевой аудитории..."
    )

    # Trigger CA analysis via analysis handler
    from avito_autoload.bot.handlers.analysis import run_ca_analysis
    await run_ca_analysis(callback.message, state, db)


@router.callback_query(F.data == "confirm")
async def on_confirm(
    callback: CallbackQuery, state: FSMContext, db: ProjectDB, file_storage: FileStorage,
) -> None:
    """User pressed 'Confirm' on any stage."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    current = await state.get_state()

    if current == ProjectStates.confirming_ca.state:
        # Move to template generation
        await state.set_state(ProjectStates.running_template)
        await callback.message.answer(
            "\u23f3 Этап 2/4: Подготовка шаблона описаний..."
        )
        from avito_autoload.bot.handlers.analysis import run_template_generation
        await run_template_generation(callback.message, state, db)

    elif current == ProjectStates.confirming_template.state:
        # Move to categorization
        await state.set_state(ProjectStates.running_categories)
        await callback.message.answer(
            "\u23f3 Этап 3/4: Категоризация товаров..."
        )
        from avito_autoload.bot.handlers.analysis import run_categorization
        await run_categorization(callback.message, state, db, file_storage)

    elif current == ProjectStates.confirming_categories.state:
        # Move to pipeline
        await state.set_state(ProjectStates.running_pipeline)
        await callback.message.answer(
            "\u23f3 Этап 4/4: Сборка файла автозагрузки..."
        )
        from avito_autoload.bot.handlers.analysis import run_pipeline
        await run_pipeline(callback.message, state, db, file_storage)


@router.callback_query(F.data == "edit")
async def on_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """User pressed 'Edit' — ask for corrections."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    current = await state.get_state()

    if current == ProjectStates.confirming_ca.state:
        await state.set_state(ProjectStates.editing_ca)
        await callback.message.answer(
            "Напиши, что нужно изменить в анализе ЦА. Я скорректирую."
        )
    elif current == ProjectStates.confirming_template.state:
        await state.set_state(ProjectStates.editing_template)
        await callback.message.answer(
            "Напиши, что нужно изменить в шаблоне описаний. Я скорректирую."
        )
    elif current == ProjectStates.confirming_categories.state:
        # Categories come from Avito API — no editing, re-show buttons
        from avito_autoload.bot.keyboards import confirm_keyboard
        await callback.message.answer(
            "Категории загружены из API Авито и не редактируются.\n"
            "Нажмите \u00abПодтвердить\u00bb чтобы перейти к сборке файла.",
            reply_markup=confirm_keyboard(),
        )


@router.callback_query(F.data == "regenerate")
async def on_regenerate(
    callback: CallbackQuery, state: FSMContext, db: ProjectDB, file_storage: FileStorage,
) -> None:
    """User wants to regenerate the file."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    await state.set_state(ProjectStates.running_pipeline)
    await callback.message.answer(
        "\u23f3 Этап 4/4: Сборка файла автозагрузки..."
    )
    from avito_autoload.bot.handlers.analysis import run_pipeline
    await run_pipeline(callback.message, state, db, file_storage)


@router.callback_query(F.data == "new_project")
async def on_new_project(callback: CallbackQuery, state: FSMContext) -> None:
    """User wants to start a new project."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    await state.clear()
    await callback.message.answer(
        "\U0001F504 Начинаем новый проект! Нажми /start"
    )
