import asyncio
import logging
import os
import shutil
from datetime import date
from pathlib import Path

import discord
from discord import app_commands
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
        success, dump_path = await self.create_backup()
        if success:
            self.logger.info("Database backup created successfully: %s", dump_path)

    async def create_backup(self) -> tuple[bool, Path | None]:
        if shutil.which("pg_dump") is None:
            self.logger.warning("Database backup skipped: pg_dump is not available")
            return False, None

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.logger.error("Database backup skipped: DATABASE_URL is not set")
            return False, None

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
            return False, dump_path

        dumps = sorted(backup_dir.glob(f"{backup_prefix}_*.sql"))
        for old_dump in dumps[:-7]:
            old_dump.unlink(missing_ok=True)

        return True, dump_path

    @app_commands.command(name="backup", description="Run a database backup now.")
    @app_commands.default_permissions(manage_guild=True)
    async def backup(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        success, dump_path = await self.create_backup()
        if success and dump_path is not None:
            await interaction.followup.send(
                f"Backup completed successfully: `{dump_path}`",
                ephemeral=True,
            )
            return

        path_text = str(dump_path) if dump_path is not None else "not created"
        await interaction.followup.send(
            f"Backup failed. Backup path: `{path_text}`",
            ephemeral=True,
        )

    @backup_task.before_loop
    async def before_backup_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DatabaseBackup(bot))
