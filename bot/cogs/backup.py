import asyncio
import logging
import os
from datetime import date
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ._utils import stamp


def _backup_dir_and_prefix() -> tuple[Path, str]:
    backup_target = Path(os.getenv("BACKUP_PATH", "/backups/eden.sql"))
    if backup_target.suffix == ".sql":
        return backup_target.parent, backup_target.stem
    return backup_target, "eden"


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
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.logger.error("Database backup skipped: DATABASE_URL is not set")
            return False, None

        backup_dir, backup_prefix = _backup_dir_and_prefix()
        dump_path = backup_dir / f"{backup_prefix}_{date.today().isoformat()}.sql"
        backup_dir.mkdir(parents=True, exist_ok=True)

        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--dbname", database_url,
            "--file", str(dump_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode().strip() or "unknown error"
            self.logger.error("Database backup failed for %s: %s", dump_path, error)
            dump_path.unlink(missing_ok=True)
            return False, dump_path

        dumps = sorted(backup_dir.glob(f"{backup_prefix}_*.sql"))
        for old_dump in dumps[:-7]:
            old_dump.unlink(missing_ok=True)

        return True, dump_path

    async def restore_backup(self, dump_path: Path) -> tuple[bool, str]:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return False, "DATABASE_URL is not set"

        if not dump_path.exists():
            return False, f"Backup file not found: `{dump_path}`"

        process = await asyncio.create_subprocess_exec(
            "psql",
            "--dbname", database_url,
            "--single-transaction",
            "--file", str(dump_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode().strip() or "unknown error"
            self.logger.error("Database restore failed from %s: %s", dump_path, error)
            return False, error

        self.logger.info("Database restored successfully from %s", dump_path)
        return True, ""

    def _list_backups(self) -> list[Path]:
        backup_dir, backup_prefix = _backup_dir_and_prefix()
        return sorted(backup_dir.glob(f"{backup_prefix}_*.sql"), reverse=True)

    @app_commands.command(name="backup", description="Run a database backup now.")
    @app_commands.default_permissions(manage_guild=True)
    async def backup(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        success, dump_path = await self.create_backup()

        embed = discord.Embed(color=discord.Color.green() if success else discord.Color.red())
        if success and dump_path is not None:
            embed.title = "✅ backup complete"
            embed.description = f"saved to `{dump_path.name}`"
        else:
            embed.title = "❌ backup failed"
            embed.description = f"path: `{dump_path}`" if dump_path else "backup was not created"

        await interaction.followup.send(embed=stamp(embed, self.bot), ephemeral=True)

    @app_commands.command(name="restore", description="Restore the database from a backup.")
    @app_commands.describe(filename="Backup filename to restore (leave blank to use the latest).")
    @app_commands.default_permissions(manage_guild=True)
    async def restore(self, interaction: discord.Interaction, filename: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        backups = self._list_backups()
        if not backups:
            await interaction.followup.send(
                embed=stamp(discord.Embed(title="📭 no backups found", color=discord.Color.orange()), self.bot),
                ephemeral=True,
            )
            return

        if filename is None:
            dump_path = backups[0]
        else:
            backup_dir = backups[0].parent
            resolved = (backup_dir / filename).resolve()
            if resolved.parent != backup_dir.resolve() or resolved not in [p.resolve() for p in backups]:
                listing = "\n".join(f"`{p.name}`" for p in backups)
                embed = discord.Embed(
                    title="❓ backup not found",
                    description=f"**available backups:**\n{listing}",
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=stamp(embed, self.bot), ephemeral=True)
                return
            dump_path = resolved

        success, error = await self.restore_backup(dump_path)
        embed = discord.Embed(color=discord.Color.green() if success else discord.Color.red())
        if success:
            embed.title = "✅ restore complete"
            embed.description = f"restored from `{dump_path.name}`"
        else:
            embed.title = "❌ restore failed"
            embed.description = f"```{error}```"

        await interaction.followup.send(embed=stamp(embed, self.bot), ephemeral=True)

    @app_commands.command(name="listbackups", description="List available database backups.")
    @app_commands.default_permissions(manage_guild=True)
    async def listbackups(self, interaction: discord.Interaction) -> None:
        backups = self._list_backups()

        embed = discord.Embed(title="🗄️ available backups", color=discord.Color.blurple())
        if not backups:
            embed.description = "no backups found"
        else:
            embed.description = "\n".join(f"`{p.name}`" for p in backups)

        await interaction.response.send_message(embed=stamp(embed, self.bot), ephemeral=True)

    @backup_task.before_loop
    async def before_backup_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DatabaseBackup(bot))
