import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from ._utils import stamp

ENV_PATH = os.path.join(os.path.dirname(__file__), "../../.env")


def _write_env_var(key: str, value: str) -> None:
    path = os.path.abspath(ENV_PATH)
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        content = pattern.sub(line, content)
    else:
        content = content.rstrip("\n") + f"\n{line}\n"
    with open(path, "w") as f:
        f.write(content)
    os.environ[key] = value


def _get_starboard_channel_id() -> int | None:
    raw = os.getenv("STARBOARD_CHANNEL_ID")
    if raw and raw.isdigit():
        return int(raw)
    return None


def _get_starboard_threshold() -> int:
    raw = os.getenv("STARBOARD_THRESHOLD", "3")
    return int(raw) if raw.isdigit() else 3


class Starboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._posted: set[int] = set()  # message IDs already on the starboard

    async def _load_posted(self) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS starboard (
                    message_id BIGINT PRIMARY KEY
                )
                """
            )
            rows = await conn.fetch("SELECT message_id FROM starboard")
        self._posted = {r["message_id"] for r in rows}

    async def _mark_posted(self, message_id: int) -> None:
        self._posted.add(message_id)
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO starboard (message_id) VALUES ($1) ON CONFLICT DO NOTHING",
                message_id,
            )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._load_posted()

    async def _get_channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException:
                return None
        return channel if isinstance(channel, discord.TextChannel) else None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) != "⭐":
            return
        if payload.message_id in self._posted:
            return

        channel_id = _get_starboard_channel_id()
        if channel_id is None:
            return

        if payload.channel_id == channel_id:
            return

        channel = await self._get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return

        star_reaction = discord.utils.get(message.reactions, emoji="⭐")
        count = star_reaction.count if star_reaction else 0
        if count < _get_starboard_threshold():
            return

        starboard_channel = await self._get_channel(channel_id)
        if starboard_channel is None:
            return

        await self._mark_posted(message.id)
        await self._post(message, count, starboard_channel)

    async def _post(self, message: discord.Message, count: int, starboard_channel: discord.TextChannel) -> None:
        embed = discord.Embed(
            description=message.content or None,
            color=discord.Color.gold(),
            timestamp=message.created_at,
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="source", value=f"[jump to message]({message.jump_url})", inline=True)
        embed.add_field(name="channel", value=message.channel.mention, inline=True)

        image_url = None
        image_attachments = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]
        if image_attachments:
            image_url = image_attachments[0].url
        if image_url is None:
            for msg_embed in message.embeds:
                if msg_embed.image and msg_embed.image.url:
                    image_url = msg_embed.image.url
                    break
                if msg_embed.thumbnail and msg_embed.thumbnail.url:
                    image_url = msg_embed.thumbnail.url
                    break
        if image_url:
            embed.set_image(url=image_url)

        await starboard_channel.send(content=f"⭐ **{count}** {message.channel.mention}", embed=stamp(embed, self.bot))

    @app_commands.command(name="set_starboard_channel", description="Set the channel where starred messages are posted.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_starboard_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        _write_env_var("STARBOARD_CHANNEL_ID", str(channel.id))
        embed = discord.Embed(
            title="✅ starboard channel set",
            description=f"starred messages will be posted to {channel.mention}",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_starboard_threshold", description="Set how many ⭐ reactions needed to reach the starboard.")
    @app_commands.describe(threshold="Minimum number of ⭐ reactions (default 3)")
    @app_commands.default_permissions(manage_guild=True)
    async def set_starboard_threshold(self, interaction: discord.Interaction, threshold: int) -> None:
        if threshold < 1:
            await interaction.response.send_message("Threshold must be at least 1.", ephemeral=True)
            return
        _write_env_var("STARBOARD_THRESHOLD", str(threshold))
        embed = discord.Embed(
            title="✅ starboard threshold set",
            description=f"messages need **{threshold}** ⭐ to reach the starboard.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Starboard(bot))
