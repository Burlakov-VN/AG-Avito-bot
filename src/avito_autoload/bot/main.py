"""Bot entry point: create Bot, Dispatcher, start polling."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from avito_autoload.bot.config import BotConfig
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Update

from avito_autoload.bot.handlers import callbacks, collect, start
from avito_autoload.bot.handlers.analysis import router as analysis_router
from avito_autoload.bot.storage.database import ProjectDB
from avito_autoload.bot.storage.files import FileStorage

logger = logging.getLogger(__name__)

# Debug catch-all router (registered last)
from aiogram import Router as _Router
_debug_router = _Router()


@_debug_router.message()
async def _debug_unhandled(message: Message, state: FSMContext) -> None:
    """Log unhandled messages for debugging."""
    current_state = await state.get_state()
    logger.warning(
        "UNHANDLED message from user=%s: type=%s, text=%r, content_type=%s, state=%s",
        message.from_user.id if message.from_user else "?",
        type(message).__name__,
        (message.text or "")[:100],
        message.content_type,
        current_state,
    )
    await message.answer(
        "Я не понял это сообщение. Отправь /start чтобы начать."
    )


async def run_bot() -> None:
    """Initialize and run the bot."""
    load_dotenv()

    config = BotConfig.from_env()
    if not config.is_configured:
        logger.error(
            "BOT_TOKEN and ANTHROPIC_API_KEY must be set in environment. "
            "Add them to .env file."
        )
        return

    # Initialize storage
    db = ProjectDB(config.db_path)
    await db.init()

    file_storage = FileStorage(config.data_dir)

    # Create bot and dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Pass dependencies via dispatcher data
    dp["config"] = config
    dp["db"] = db
    dp["file_storage"] = file_storage

    # Register routers
    dp.include_router(start.router)
    dp.include_router(collect.router)
    dp.include_router(callbacks.router)
    dp.include_router(analysis_router)
    dp.include_router(_debug_router)  # catch-all: must be last

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


def main() -> None:
    """CLI entry point for the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
