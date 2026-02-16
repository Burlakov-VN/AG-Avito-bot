"""File management for bot: download, store, cleanup."""

import logging
from pathlib import Path

from aiogram import Bot

logger = logging.getLogger(__name__)


class FileStorage:
    """Manages uploaded files for bot projects."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def project_dir(self, user_id: int, project_id: int) -> Path:
        """Get directory for a specific project."""
        path = self.data_dir / str(user_id) / str(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def download_file(
        self,
        bot: Bot,
        file_id: str,
        user_id: int,
        project_id: int,
        filename: str,
    ) -> Path:
        """Download a Telegram file and save it locally."""
        dest_dir = self.project_dir(user_id, project_id)
        dest_path = dest_dir / filename

        file = await bot.get_file(file_id)
        assert file.file_path is not None
        await bot.download_file(file.file_path, dest_path)

        logger.info("Downloaded file: %s -> %s", filename, dest_path)
        return dest_path

    def get_output_path(self, user_id: int, project_id: int) -> Path:
        """Get path for the output autoload file."""
        return self.project_dir(user_id, project_id) / "avito_autoload.xlsx"

    def cleanup_project(self, user_id: int, project_id: int) -> None:
        """Remove all files for a project."""
        project_path = self.project_dir(user_id, project_id)
        if project_path.exists():
            import shutil
            shutil.rmtree(project_path)
            logger.info("Cleaned up project files: %s", project_path)
