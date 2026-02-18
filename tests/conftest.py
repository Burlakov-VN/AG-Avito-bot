"""Shared fixtures and mock factories for AG-Avito-bot tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from avito_autoload.bot.storage.database import ProjectDB
from avito_autoload.bot.storage.files import FileStorage

# ── Test data constants ──────────────────────────────────────

TEST_USER_ID = 12345
TEST_CHAT_ID = 12345
TEST_PROJECT_ID = 1
TEST_NICHE = "Запчасти для грузовиков"

TEST_PRICELIST_TEXT = (
    "Код\tАртикул\tНаименование\tЦена\n"
    "50007026\t7170290\tСтекло 7170290\t60 830,00\n"
    "222002\tC4934862\tВал коленчатый Cummins\t76 021,00"
)

TEST_COMPETITORS_TEXT = (
    "Заголовок: Запчасти для грузовиков в наличии\n"
    "Описание: Продаём запчасти для КАМАЗ, МАЗ, Volvo. Доставка по РФ."
)

TEST_ADDRESSES = (
    "г. Москва, ул. Ленина, 10\n"
    "г. Казань, пр. Мира, 25"
)

TEST_MANAGERS = (
    "г. Москва, ул. Ленина, 10 — Алексей\n"
    "г. Казань, пр. Мира, 25 — Ольга"
)

TEST_PHONE = "+7 (999) 123-45-67"

TEST_COMPANY_INFO = (
    "Компания АвтоТрак, продаём запчасти для грузовиков с 2010 года. "
    "Преимущество — наличие на складе, отправка в день заказа."
)

TEST_TITLE_INFO = "Начинать с артикула, затем бренд и название детали"

# Fake CA analysis result
TEST_CA_DATA = {
    "segments": [
        {"name": "Частники", "description": "Владельцы грузовиков"},
        {"name": "Сервисы", "description": "Автосервисы"},
    ],
    "main_pain": "Машина стоит — деньги теряются",
    "pain_points": ["Долгая доставка", "Нет в наличии"],
    "top_usp": ["В наличии", "Быстрая отправка"],
    "objections": ["Дорого", "Не оригинал"],
    "keywords": ["запчасти грузовик", "КАМАЗ"],
    "tone": "Уверенный, экспертный",
    "full_analysis": "# Анализ ЦА\n\nТекст анализа...",
}

# Fake template result
TEST_TEMPLATE_DATA = {
    "description_structure": [
        {"block_name": "Заголовок-крючок"},
        {"block_name": "О товаре"},
    ],
    "headline_variants": ["В НАЛИЧИИ", "СРОЧНО"],
    "company_block": "О компании АвтоТрак",
    "description_prompt": "prompt text",
    "full_template": "# Шаблон\n\nТекст шаблона...",
    "summary": "Шаблон для запчастей",
}

# Fake categories result
TEST_CATEGORIES_DATA = {
    "root_category": "Запчасти и аксессуары",
    "sections": [
        {
            "goods_type": "Запчасти",
            "product_types": [{"spare_part_types": ["Двигатель", "Кузов"]}],
        },
    ],
}


# ── Mock factories ───────────────────────────────────────────


def make_message(
    text: str = "",
    user_id: int = TEST_USER_ID,
    chat_id: int | None = None,
) -> MagicMock:
    """Create a mock aiogram Message object."""
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    msg.answer_document = AsyncMock()

    msg.from_user = MagicMock()
    msg.from_user.id = user_id

    msg.chat = MagicMock()
    msg.chat.id = chat_id or user_id

    msg.document = None
    msg.content_type = "text"

    return msg


def make_document_message(
    file_name: str = "pricelist.xlsx",
    file_id: str = "test_file_id_123",
    user_id: int = TEST_USER_ID,
) -> MagicMock:
    """Create a mock Message with a document attachment."""
    msg = make_message(text=None, user_id=user_id)
    msg.content_type = "document"
    msg.document = MagicMock()
    msg.document.file_name = file_name
    msg.document.file_id = file_id
    return msg


def make_callback(
    data: str = "confirm",
    user_id: int = TEST_USER_ID,
) -> MagicMock:
    """Create a mock aiogram CallbackQuery object."""
    cb = MagicMock()
    cb.data = data
    cb.answer = AsyncMock()

    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    cb.message.answer_document = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = user_id

    cb.from_user = MagicMock()
    cb.from_user.id = user_id

    return cb


def make_state(
    current_state: str | None = None,
    data: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock FSMContext that tracks state and data."""
    state = MagicMock()
    _state_value = current_state
    _data = dict(data or {})

    async def get_state():
        return _state_value

    async def set_state(new_state):
        nonlocal _state_value
        _state_value = new_state

    async def get_data():
        return dict(_data)

    async def update_data(**kwargs):
        _data.update(kwargs)
        return dict(_data)

    async def clear():
        nonlocal _state_value
        _state_value = None
        _data.clear()

    state.get_state = get_state
    state.set_state = set_state
    state.get_data = get_data
    state.update_data = update_data
    state.clear = clear

    return state


# ── Pytest fixtures ──────────────────────────────────────────


@pytest.fixture
async def test_db(tmp_path) -> ProjectDB:
    """Real ProjectDB on a temporary SQLite file."""
    db = ProjectDB(tmp_path / "test.db")
    await db.init()
    yield db
    await db.close()


@pytest.fixture
def test_file_storage(tmp_path) -> FileStorage:
    """FileStorage on a temporary directory."""
    return FileStorage(tmp_path / "files")


@pytest.fixture
def mock_bot() -> MagicMock:
    """Mock aiogram Bot."""
    bot = MagicMock()
    mock_file = MagicMock()
    mock_file.file_path = "photos/file_0.xlsx"
    bot.get_file = AsyncMock(return_value=mock_file)
    bot.download_file = AsyncMock()
    return bot
