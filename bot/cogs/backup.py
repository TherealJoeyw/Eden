import asyncio
import logging
import os
from datetime import date
from pathlib import Path

from discord.ext import commands, tasks


class DatabaseBackup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.backup_task.start()

    def cog_unload(self) -> None:
        self.backup_task.cancel()

    @tasks.loop(hours=24)
    async def backup_task(self) -> None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.logger.error("Database backup skipped: DATABASE_URL is not set")
            return

        backup_target = Path(os.getenv("BACKUP_PATH", "/backups/eden.sql"))
        if backup_target.suffix == ".sql":
            backup_dir = backup_target.parent
            backup_prefix = backup_target.stem
        else:
            backup_dir = backup_target
            backup_prefix = "eden"

        dump_path = backup_dir / f"{backup_prefix}_{date.today().isoformat()}.sql"
        backup_dir.mkdir(parents=True, exist_ok=True)

        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--dbname",
            database_url,
            "--file",
            str(dump_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode().strip() or "unknown error"
            self.logger.error("Database backup failed for %s: %s", dump_path, error)
            return

        dumps = sorted(backup_dir.glob(f"{backup_prefix}_*.sql"))
        for old_dump in dumps[:-7]:
            old_dump.unlink(missing_ok=True)

        self.logger.info("Database backup created successfully: %s", dump_path)

    @backup_task.before_loop
    async def before_backup_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DatabaseBackup(bot))
