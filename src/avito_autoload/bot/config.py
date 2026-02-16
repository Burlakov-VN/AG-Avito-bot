"""Bot configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BotConfig:
    """Configuration for the Telegram bot."""

    bot_token: str = ""
    anthropic_api_key: str = ""
    avito_client_id: str = ""
    avito_client_secret: str = ""
    data_dir: Path = field(default_factory=lambda: Path("data/bot"))
    db_path: Path = field(default_factory=lambda: Path("data/bot/bot.db"))

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        data_dir = Path(os.environ.get("BOT_DATA_DIR", "data/bot"))
        return cls(
            bot_token=os.environ.get("BOT_TOKEN", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            avito_client_id=os.environ.get("AVITO_CLIENT_ID", ""),
            avito_client_secret=os.environ.get("AVITO_CLIENT_SECRET", ""),
            data_dir=data_dir,
            db_path=data_dir / "bot.db",
        )

    @property
    def is_configured(self) -> bool:
        """Check that minimal required config is present."""
        return bool(self.bot_token and self.anthropic_api_key)
