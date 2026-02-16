"""Tests for Telegram bot modules."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avito_autoload.bot.config import BotConfig
from avito_autoload.bot.keyboards import (
    complete_keyboard,
    confirm_keyboard,
    start_plan_keyboard,
)
from avito_autoload.bot.states import ProjectStates
from avito_autoload.models.avito_row import InputRow


# === Config ===


def test_bot_config_from_env():
    with patch.dict("os.environ", {
        "BOT_TOKEN": "123:ABC",
        "ANTHROPIC_API_KEY": "sk-test",
    }):
        config = BotConfig.from_env()
        assert config.bot_token == "123:ABC"
        assert config.anthropic_api_key == "sk-test"
        assert config.is_configured is True


def test_bot_config_not_configured():
    with patch.dict("os.environ", {}, clear=True):
        config = BotConfig.from_env()
        assert config.is_configured is False


def test_bot_config_data_dir():
    with patch.dict("os.environ", {"BOT_DATA_DIR": "/tmp/test_bot"}):
        config = BotConfig.from_env()
        assert config.data_dir == Path("/tmp/test_bot")
        assert config.db_path == Path("/tmp/test_bot/bot.db")


# === States ===


def test_states_exist():
    assert ProjectStates.waiting_niche is not None
    assert ProjectStates.waiting_pricelist is not None
    assert ProjectStates.waiting_competitors is not None
    assert ProjectStates.confirming_plan is not None
    assert ProjectStates.running_ca_analysis is not None
    assert ProjectStates.confirming_ca is not None
    assert ProjectStates.editing_ca is not None
    assert ProjectStates.running_template is not None
    assert ProjectStates.confirming_template is not None
    assert ProjectStates.editing_template is not None
    assert ProjectStates.running_categories is not None
    assert ProjectStates.confirming_categories is not None
    assert ProjectStates.running_pipeline is not None
    assert ProjectStates.complete is not None


# === Keyboards ===


def test_start_plan_keyboard():
    kb = start_plan_keyboard()
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "plan_start"


def test_confirm_keyboard():
    kb = confirm_keyboard()
    assert len(kb.inline_keyboard) == 1
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "confirm"
    assert buttons[1].callback_data == "edit"


def test_complete_keyboard():
    kb = complete_keyboard()
    buttons = kb.inline_keyboard[0]
    assert buttons[0].callback_data == "regenerate"
    assert buttons[1].callback_data == "new_project"


# === Database ===


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.mark.asyncio
async def test_database_create_and_get(tmp_db_path):
    from avito_autoload.bot.storage.database import ProjectDB

    db = ProjectDB(tmp_db_path)
    await db.init()

    project_id = await db.create_project(user_id=12345)
    assert project_id is not None
    assert project_id > 0

    project = await db.get_active_project(user_id=12345)
    assert project is not None
    assert project["user_id"] == 12345
    assert project["id"] == project_id

    await db.close()


@pytest.mark.asyncio
async def test_database_update(tmp_db_path):
    from avito_autoload.bot.storage.database import ProjectDB

    db = ProjectDB(tmp_db_path)
    await db.init()

    project_id = await db.create_project(user_id=999)
    await db.update_project(project_id, niche="Запчасти для грузовиков")

    project = await db.get_active_project(user_id=999)
    assert project["niche"] == "Запчасти для грузовиков"

    await db.close()


@pytest.mark.asyncio
async def test_database_json_field(tmp_db_path):
    from avito_autoload.bot.storage.database import ProjectDB

    db = ProjectDB(tmp_db_path)
    await db.init()

    project_id = await db.create_project(user_id=111)
    test_data = {"segments": [{"name": "Test"}], "main_pain": "Pain"}
    await db.set_json_field(project_id, "ca_analysis", test_data)

    loaded = await db.get_json_field(project_id, "ca_analysis")
    assert loaded == test_data

    await db.close()


# === File Storage ===


def test_file_storage_project_dir(tmp_path):
    from avito_autoload.bot.storage.files import FileStorage

    storage = FileStorage(tmp_path / "data")
    project_dir = storage.project_dir(user_id=123, project_id=1)
    assert project_dir.exists()
    assert "123" in str(project_dir)
    assert "1" in str(project_dir)


def test_file_storage_output_path(tmp_path):
    from avito_autoload.bot.storage.files import FileStorage

    storage = FileStorage(tmp_path / "data")
    output = storage.get_output_path(user_id=123, project_id=1)
    assert output.name == "avito_autoload.xlsx"


# === CA Analyzer ===


def test_ca_format_summary():
    from avito_autoload.bot.services.ca_analyzer import format_ca_summary

    ca_data = {
        "segments": [
            {"name": "Частники", "description": "Владельцы грузовиков"},
            {"name": "Сервисы", "description": "Автосервисы"},
        ],
        "main_pain": "Машина стоит — деньги теряются",
        "top_usp": ["В наличии", "Быстрая отправка"],
    }

    summary = format_ca_summary(ca_data, "Запчасти для грузовиков")
    assert "Частники" in summary
    assert "Сервисы" in summary
    assert "Машина стоит" in summary
    assert "В наличии" in summary


# === Template Builder ===


def test_template_format_summary():
    from avito_autoload.bot.services.template_builder import format_template_summary

    template = {
        "description_structure": [
            {"block_name": "Заголовок-крючок"},
            {"block_name": "О товаре"},
        ],
        "headline_variants": ["❗️В НАЛИЧИИ❗️", "⚡️СРОЧНО⚡️"],
        "summary": "Шаблон для запчастей",
    }

    text = format_template_summary(template)
    assert "Заголовок-крючок" in text
    assert "О товаре" in text
    assert "В НАЛИЧИИ" in text


# === Category Fetcher ===


def test_categories_format_summary():
    from avito_autoload.bot.services.category_fetcher import format_categories_summary

    categories = {
        "root_category": "Запчасти и аксессуары",
        "sections": [
            {"goods_type": "Запчасти", "product_types": [
                {"spare_part_types": ["Двигатель", "Кузов"]},
            ]},
            {"goods_type": "Масла", "categories": ["Моторные", "Трансмиссионные"]},
        ],
    }

    text = format_categories_summary(categories)
    assert "Запчасти и аксессуары" in text
    assert "Запчасти" in text
    assert "Масла" in text


# === Pipeline Runner ===


def test_pipeline_format_result():
    from avito_autoload.bot.services.pipeline_runner import format_pipeline_result

    result = {
        "total_items": 39,
        "total_rows": 78,
        "cities": 2,
        "descriptions": 39,
        "categorized": 35,
        "total_categorized": 39,
    }
    text = format_pipeline_result(result)
    assert "39" in text
    assert "78" in text
    assert "готов" in text.lower()


def test_pipeline_format_error():
    from avito_autoload.bot.services.pipeline_runner import format_pipeline_result

    result = {"error": "Нет данных"}
    text = format_pipeline_result(result)
    assert "Нет данных" in text


# === Parametrized describer ===


def test_generate_descriptions_custom_company_block(tmp_path):
    """Test that custom company_block is used."""
    from avito_autoload.describer.llm_describer import generate_descriptions
    from avito_autoload.categorizers.llm_categorizer import CategoryResult
    from avito_autoload.describer.cache import DescriptionCache

    cache = DescriptionCache(cache_path=tmp_path / "desc_cache.json")

    rows = [InputRow(code="001", article="TEST123", name="Test part", price=1000)]
    category_map = {"TEST123": CategoryResult(spare_part_type="Двигатель")}

    custom_block = "CUSTOM COMPANY BLOCK"

    with patch("avito_autoload.describer.llm_describer._call_anthropic") as mock_api:
        mock_api.return_value = json.dumps([{"index": 1, "description": "Product desc"}])

        result = generate_descriptions(
            rows, category_map, cache, company_block=custom_block,
        )

        assert "TEST123" in result
        assert "CUSTOM COMPANY BLOCK" in result["TEST123"]
        assert "Product desc" in result["TEST123"]
