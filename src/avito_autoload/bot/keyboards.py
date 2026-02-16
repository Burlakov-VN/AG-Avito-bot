"""Inline keyboards for bot interactions."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_plan_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with 'Start' button for plan confirmation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u25b6\ufe0f Начать", callback_data="plan_start")],
    ])


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with 'Confirm' and 'Edit' buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Подтвердить", callback_data="confirm"),
            InlineKeyboardButton(text="\u270f\ufe0f Внести правки", callback_data="edit"),
        ],
    ])


def complete_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after file delivery."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001F504 Сгенерировать заново", callback_data="regenerate"),
            InlineKeyboardButton(text="\U0001F4CB Новый прайс", callback_data="new_project"),
        ],
    ])
