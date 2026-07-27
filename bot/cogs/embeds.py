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


_last_reply: dict[int, str] = {}


class AutoEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        fixed = _extract_fixed(message.content)
        if not fixed:
            return

        reply_text = " ".join(fixed)

        if _last_reply.get(message.channel.id) == reply_text:
            return

        _last_reply[message.channel.id] = reply_text
        await message.reply(reply_text, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoEmbed(bot))
