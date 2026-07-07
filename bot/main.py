import os
import random
from datetime import datetime
from pathlib import Path

import asyncpg
import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.roles import RoleSelectView
from cogs.tickets import CloseTicketView, OpenTicketView

load_dotenv()


class EdenBot(commands.Bot):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)
        self.guild_id = guild_id
        self.db_pool: asyncpg.Pool | None = None
        self.started_at: datetime | None = None
        self.instance_id: str = format(random.randint(0, 0xFFFF), "04X")

    async def setup_hook(self) -> None:
        self.started_at = discord.utils.utcnow()

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")

        self.db_pool = await asyncpg.create_pool(dsn=database_url)

        self.add_view(RoleSelectView([]))
        self.add_view(CloseTicketView())
        self.add_view(OpenTicketView())

        cogs_dir = Path(__file__).parent / "cogs"
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.stem.startswith("_"):
                continue
            await self.load_extension(f"cogs.{cog_file.stem}")

        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"Synced {len(synced)} guild commands")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.user and self.user.mentioned_in(message):
            await message.reply("pong 🏓")

    async def close(self) -> None:
        if self.db_pool is not None:
            await self.db_pool.close()
        await super().close()



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
