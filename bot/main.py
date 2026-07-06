import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from cogs.roles import RoleSelectView
from cogs.tickets import CloseTicketView, OpenTicketView

load_dotenv()

logging.basicConfig(level=logging.INFO)


class EdenBot(commands.Bot):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.guild_id = guild_id
        self.db_pool: asyncpg.Pool | None = None
        self.started_at: datetime | None = None

    async def setup_hook(self) -> None:
        self.started_at = discord.utils.utcnow()

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")

        self.db_pool = await asyncpg.create_pool(dsn=database_url)

        self.add_view(RoleSelectView([]))
        self.add_view(CloseTicketView())
        self.add_view(OpenTicketView())

        self.tree.add_command(self.diagnostics)

        cogs_dir = Path(__file__).parent / "cogs"
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.stem.startswith("_"):
                continue
            await self.load_extension(f"cogs.{cog_file.stem}")

        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        logging.info("Synced %s guild commands", len(synced))

    async def close(self) -> None:
        if self.db_pool is not None:
            await self.db_pool.close()
        await super().close()

    @app_commands.command(name="diagnostics", description="Show bot diagnostics.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def diagnostics(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.latency * 1000, 2)

        db_status = "Unavailable"
        if self.db_pool is not None:
            try:
                async with self.db_pool.acquire() as connection:
                    result = await connection.fetchval("SELECT 1")
                db_status = "Connected" if result == 1 else "Unexpected response"
            except Exception:
                db_status = "Disconnected"

        command_count = sum(1 for _ in self.tree.walk_commands())
        cog_count = len(self.cogs)

        uptime = "Unknown"
        if self.started_at is not None:
            elapsed = discord.utils.utcnow() - self.started_at
            uptime = str(timedelta(seconds=int(elapsed.total_seconds())))

        embed = discord.Embed(title="Diagnostics", color=discord.Color.blurple())
        embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=False)
        embed.add_field(name="Database", value=db_status, inline=False)
        embed.add_field(name="Loaded cogs", value=str(cog_count), inline=False)
        embed.add_field(name="Slash commands", value=str(command_count), inline=False)
        embed.add_field(name="Uptime", value=uptime, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


def create_bot() -> EdenBot:
    token = os.getenv("DISCORD_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")
    if not guild_id:
        raise RuntimeError("DISCORD_GUILD_ID is required")

    return EdenBot(guild_id=int(guild_id))


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")

    bot = create_bot()
    bot.run(token)


if __name__ == "__main__":
    main()
