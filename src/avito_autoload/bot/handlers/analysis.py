"""Handlers for analysis stages: CA, template, categories, pipeline."""

import io
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from avito_autoload.bot.keyboards import complete_keyboard, confirm_keyboard
from avito_autoload.bot.states import ProjectStates
from avito_autoload.bot.storage.database import ProjectDB
from avito_autoload.bot.storage.files import FileStorage

logger = logging.getLogger(__name__)

router = Router()

DEFAULT_CONFIG_DIR = Path("config")


# ──────────────────────────────────────────────
# STAGE 1: CA Analysis
# ──────────────────────────────────────────────

async def run_ca_analysis(
    message: Message, state: FSMContext, db: ProjectDB,
) -> None:
    """Run CA analysis and send results."""
    from avito_autoload.bot.services.ca_analyzer import (
        analyze_target_audience,
        format_ca_summary,
    )

    data = await state.get_data()
    project_id = data["project_id"]

    # Get project info from DB
    project = await db.get_active_project(message.chat.id)
    niche = project.get("niche", "") if project else data.get("niche", "")
    competitors_path = project.get("competitors_path") if project else None

    try:
        await message.answer(
            f"\u23f3 Анализирую нишу \u00ab{niche}\u00bb, изучаю конкурентов..."
        )

        ca_data = await analyze_target_audience(niche, competitors_path)

        # Save to DB
        await db.set_json_field(project_id, "ca_analysis", ca_data)
        await state.update_data(ca_data=ca_data, niche=niche)

        # Format and send summary
        summary = format_ca_summary(ca_data, niche)
        await message.answer(summary, reply_markup=confirm_keyboard())

        # Send full analysis as PDF file if available
        full_analysis = ca_data.get("full_analysis", "")
        if full_analysis:
            from avito_autoload.bot.utils.pdf import markdown_to_pdf
            pdf_bytes = markdown_to_pdf(full_analysis, title=f"Анализ ЦА: {niche}")
            doc = BufferedInputFile(pdf_bytes, filename="ca_analysis.pdf")
            await message.answer_document(doc)

        await state.set_state(ProjectStates.confirming_ca)

    except Exception:
        logger.exception("CA analysis failed")
        await message.answer(
            "\u26a0\ufe0f Произошла ошибка при анализе ЦА. Попробую ещё раз через 30 секунд..."
        )
        import asyncio
        await asyncio.sleep(30)
        await run_ca_analysis(message, state, db)


# Handle edit corrections for CA
@router.message(ProjectStates.editing_ca, F.text)
async def handle_ca_edit(
    message: Message, state: FSMContext, db: ProjectDB,
) -> None:
    """User sent corrections for CA analysis."""
    from avito_autoload.bot.services.ca_analyzer import (
        analyze_target_audience,
        format_ca_summary,
    )

    data = await state.get_data()
    project_id = data["project_id"]
    niche = data.get("niche", "")

    corrections = message.text
    project = await db.get_active_project(message.from_user.id)
    competitors_path = project.get("competitors_path") if project else None

    await message.answer("\u23f3 Корректирую анализ ЦА...")

    # Re-run with corrections appended to niche
    niche_with_corrections = f"{niche}\n\nДополнительные указания: {corrections}"
    ca_data = await analyze_target_audience(niche_with_corrections, competitors_path)

    await db.set_json_field(project_id, "ca_analysis", ca_data)
    await state.update_data(ca_data=ca_data)

    summary = format_ca_summary(ca_data, niche)
    await message.answer(summary, reply_markup=confirm_keyboard())

    full_analysis = ca_data.get("full_analysis", "")
    if full_analysis:
        from avito_autoload.bot.utils.pdf import markdown_to_pdf
        pdf_bytes = markdown_to_pdf(full_analysis, title=f"Анализ ЦА: {niche}")
        doc = BufferedInputFile(pdf_bytes, filename="ca_analysis.pdf")
        await message.answer_document(doc)

    await state.set_state(ProjectStates.confirming_ca)


# ──────────────────────────────────────────────
# STAGE 2: Template Generation
# ──────────────────────────────────────────────

async def run_template_generation(
    message: Message, state: FSMContext, db: ProjectDB,
) -> None:
    """Run template generation and send results."""
    from avito_autoload.bot.services.competitor_analyzer import analyze_competitors
    from avito_autoload.bot.services.template_builder import (
        build_template,
        format_template_summary,
    )

    data = await state.get_data()
    project_id = data["project_id"]
    niche = data.get("niche", "")
    ca_data = data.get("ca_data", {})

    project = await db.get_active_project(message.chat.id)
    competitors_path = project.get("competitors_path") if project else None

    try:
        # Step 1: Analyze competitors
        competitor_data = {}
        if competitors_path:
            await message.answer(
                "\u23f3 Анализирую объявления конкурентов, определяю лучшие практики..."
            )
            competitor_data = await analyze_competitors(niche, competitors_path)

        # Step 2: Build template
        template = await build_template(niche, ca_data, competitor_data)

        # Save
        await db.set_json_field(project_id, "template_config", template)
        await state.update_data(template_config=template)

        # Format and send
        summary = format_template_summary(template)
        await message.answer(summary, reply_markup=confirm_keyboard())

        # Send template as PDF
        full_template = template.get("full_template", "")
        if full_template:
            from avito_autoload.bot.utils.pdf import markdown_to_pdf
            pdf_bytes = markdown_to_pdf(full_template, title=f"Шаблон описаний: {niche}")
            doc = BufferedInputFile(pdf_bytes, filename="template.pdf")
            await message.answer_document(doc)

        await state.set_state(ProjectStates.confirming_template)

    except Exception:
        logger.exception("Template generation failed")
        await message.answer(
            "\u26a0\ufe0f Ошибка при создании шаблона. Попробую ещё раз через 30 секунд..."
        )
        import asyncio
        await asyncio.sleep(30)
        await run_template_generation(message, state, db)


# Handle edit corrections for template
@router.message(ProjectStates.editing_template, F.text)
async def handle_template_edit(
    message: Message, state: FSMContext, db: ProjectDB,
) -> None:
    """User sent corrections for template."""
    from avito_autoload.bot.services.competitor_analyzer import analyze_competitors
    from avito_autoload.bot.services.template_builder import (
        build_template,
        format_template_summary,
    )

    data = await state.get_data()
    project_id = data["project_id"]
    niche = data.get("niche", "")
    ca_data = data.get("ca_data", {})
    project = await db.get_active_project(message.from_user.id)
    competitors_path = project.get("competitors_path") if project else None

    corrections = message.text
    await message.answer("\u23f3 Корректирую шаблон...")

    # Add corrections to CA data for template rebuild
    ca_data_with_corrections = {**ca_data, "template_corrections": corrections}

    competitor_data = {}
    if competitors_path:
        competitor_data = await analyze_competitors(niche, competitors_path)

    template = await build_template(niche, ca_data_with_corrections, competitor_data)

    await db.set_json_field(project_id, "template_config", template)
    await state.update_data(template_config=template)

    summary = format_template_summary(template)
    await message.answer(summary, reply_markup=confirm_keyboard())

    full_template = template.get("full_template", "")
    if full_template:
        from avito_autoload.bot.utils.pdf import markdown_to_pdf
        pdf_bytes = markdown_to_pdf(full_template, title=f"Шаблон описаний: {niche}")
        doc = BufferedInputFile(pdf_bytes, filename="template.pdf")
        await message.answer_document(doc)

    await state.set_state(ProjectStates.confirming_template)


# ──────────────────────────────────────────────
# STAGE 3: Categorization
# ──────────────────────────────────────────────

async def run_categorization(
    message: Message, state: FSMContext, db: ProjectDB, file_storage: FileStorage,
) -> None:
    """Run category fetching from Avito API."""
    from avito_autoload.bot.services.category_fetcher import (
        fetch_categories_for_niche,
        format_categories_summary,
    )

    data = await state.get_data()
    project_id = data["project_id"]
    niche = data.get("niche", "")

    try:
        project = await db.get_active_project(message.chat.id)
        pricelist_path = project.get("pricelist_path") if project else None

        # Count items
        item_count = 0
        if pricelist_path:
            try:
                from avito_autoload.parsers.xlsx_parser import parse_xlsx
                rows = parse_xlsx(Path(pricelist_path))
                item_count = len(rows)
            except Exception:
                pass

        await message.answer(
            f"\u23f3 Загружаю категории из API Авито, классифицирую "
            f"{item_count or 'все'} позиций..."
        )

        # Fetch categories
        output_dir = DEFAULT_CONFIG_DIR
        if pricelist_path:
            output_dir = Path(pricelist_path).parent

        categories = await fetch_categories_for_niche(niche, output_dir)

        # Save
        await db.set_json_field(project_id, "categories_config", categories)
        await state.update_data(categories_config=categories)

        # Format and send
        summary = format_categories_summary(categories)
        await message.answer(summary, reply_markup=confirm_keyboard())

        # Send categories as PDF
        from avito_autoload.bot.utils.pdf import markdown_to_pdf
        categories_text = summary.replace("\u2705", "-").replace("\u274c", "-")
        pdf_bytes = markdown_to_pdf(categories_text, title=f"Категоризация: {niche}")
        doc = BufferedInputFile(pdf_bytes, filename="categories.pdf")
        await message.answer_document(doc)

        await state.set_state(ProjectStates.confirming_categories)

    except Exception:
        logger.exception("Categorization failed")
        await message.answer(
            "\u26a0\ufe0f Ошибка при категоризации. Попробую ещё раз через 30 секунд..."
        )
        import asyncio
        await asyncio.sleep(30)
        await run_categorization(message, state, db, file_storage)


# ──────────────────────────────────────────────
# STAGE 4: Pipeline (file assembly)
# ──────────────────────────────────────────────

async def run_pipeline(
    message: Message, state: FSMContext, db: ProjectDB, file_storage: FileStorage,
) -> None:
    """Run the full pipeline and send the result file."""
    from avito_autoload.bot.services.pipeline_runner import (
        format_pipeline_result,
        run_pipeline_async,
    )

    data = await state.get_data()
    project_id = data["project_id"]
    template_config = data.get("template_config")
    categories_config = data.get("categories_config", {})

    project = await db.get_active_project(message.chat.id)
    pricelist_path = project.get("pricelist_path") if project else None

    if not pricelist_path:
        await message.answer("\u26a0\ufe0f Прайс-лист не найден. Начните заново /start")
        return

    output_path = file_storage.get_output_path(message.chat.id, project_id)

    try:
        progress_msg = await message.answer(
            "\u23f3 Генерирую описания, собираю файл...\n"
            "Это может занять несколько минут."
        )

        # If no categories from API, try loading from config
        if not categories_config or not categories_config.get("sections"):
            try:
                from avito_autoload.config.settings import load_json_config
                categories_config = load_json_config(DEFAULT_CONFIG_DIR, "avito_categories.json")
                await state.update_data(categories_config=categories_config)
            except FileNotFoundError:
                pass

        result = await run_pipeline_async(
            pricelist_path=Path(pricelist_path),
            output_path=output_path,
            categories_config=categories_config,
            config_dir=DEFAULT_CONFIG_DIR,
            template_config=template_config,
        )

        # Update DB
        await db.update_project(project_id, output_path=str(output_path))

        # Send result text
        result_text = format_pipeline_result(result)
        await message.answer(result_text, reply_markup=complete_keyboard())

        # Send the file
        if output_path.exists():
            doc = BufferedInputFile(
                output_path.read_bytes(),
                filename="avito_autoload.xlsx",
            )
            await message.answer_document(doc)

        await state.set_state(ProjectStates.complete)

    except Exception:
        logger.exception("Pipeline failed")
        await message.answer(
            "\u26a0\ufe0f Ошибка при сборке файла. Попробую ещё раз через 30 секунд..."
        )
        import asyncio
        await asyncio.sleep(30)
        await run_pipeline(message, state, db, file_storage)
