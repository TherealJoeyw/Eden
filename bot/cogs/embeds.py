import re
import time

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


# message_id -> timestamp — prevents double-firing on the same message
_processed: dict[int, float] = {}
# (channel_id, reply_text) -> timestamp — prevents repeat replies for same URL
_recent_replies: dict[tuple[int, str], float] = {}
_DEDUP_WINDOW = 30.0


class AutoEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        now = time.monotonic()

        if message.id in _processed:
            return
        _processed[message.id] = now

        # evict entries older than 60s to keep memory bounded
        cutoff = now - 60.0
        for mid in [k for k, v in _processed.items() if v < cutoff]:
            del _processed[mid]

        fixed = _extract_fixed(message.content)
        if not fixed:
            return

        reply_text = " ".join(fixed)

        key = (message.channel.id, reply_text)
        if now - _recent_replies.get(key, 0) < _DEDUP_WINDOW:
            return

        _recent_replies[key] = now
        await message.reply(reply_text, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoEmbed(bot))
