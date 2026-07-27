import re

import discord
from discord import app_commands
from discord.ext import commands

RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\S+", re.IGNORECASE), "fxtwitter.com"),
    (re.compile(r"https?://(?:www\.)?instagram\.com/\S+", re.IGNORECASE), "ddinstagram.com"),
    (re.compile(r"https?://(?:www\.)?(?:tiktok\.com|vm\.tiktok\.com)/\S+", re.IGNORECASE), "vxtiktok.com"),
]

_DOMAIN = re.compile(r"https?://(?:www\.)?([^/]+)")


def _fix(url: str) -> str | None:
    for pattern, replacement in RULES:
        if pattern.match(url):
            return _DOMAIN.sub(lambda m: m.group(0).replace(m.group(1), replacement), url, count=1)
    return None


def _extract_fixed(content: str) -> list[str]:
    urls = re.findall(r"https?://\S+", content)
    fixed = []
    for url in urls:
        result = _fix(url.rstrip(".,)>\"'"))
        if result and result not in fixed:
            fixed.append(result)
    return fixed


class AutoEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _claim(self, message_id: int) -> bool:
        """Returns True if this instance should handle the message, False if already claimed."""
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return True
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embed_handled (
                    message_id BIGINT PRIMARY KEY,
                    handled_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            result = await conn.execute(
                "INSERT INTO embed_handled (message_id) VALUES ($1) ON CONFLICT DO NOTHING",
                message_id,
            )
        return result == "INSERT 0 1"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        fixed = _extract_fixed(message.content)
        if not fixed:
            return

        if not await self._claim(message.id):
            return

        await message.edit(suppress=True)
        await message.reply(" ".join(fixed), mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoEmbed(bot))
