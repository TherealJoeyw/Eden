import os
import re

import discord
from discord import app_commands
from discord.ext import commands

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


def _get_log_channel_id() -> int | None:
    raw = os.getenv("LOG_CHANNEL_ID")
    if raw and raw.isdigit():
        return int(raw)
    return None


class MessageLogging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel_id = _get_log_channel_id()
        if channel_id is None:
            return None
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @app_commands.command(name="set_log_channel", description="Set the channel used for message logs.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        _write_env_var("LOG_CHANNEL_ID", str(channel.id))

        embed = discord.Embed(
            title="✅ log channel updated",
            description=f"message logs will now be sent to {channel.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        log_channel = self._get_log_channel(message.guild)
        if log_channel is None:
            return

        embed = discord.Embed(title="🗑️ message deleted", color=discord.Color.red())
        embed.add_field(name="👤 author", value=message.author.mention, inline=True)
        embed.add_field(name="📍 channel", value=message.channel.mention, inline=True)
        embed.add_field(name="💬 content", value=message.content or "*no content*", inline=False)
        embed.set_footer(text=f"user id: {message.author.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return

        log_channel = self._get_log_channel(before.guild)
        if log_channel is None:
            return

        embed = discord.Embed(title="✏️ message edited", color=discord.Color.orange())
        embed.add_field(name="👤 author", value=before.author.mention, inline=True)
        embed.add_field(name="📍 channel", value=before.channel.mention, inline=True)
        embed.add_field(name="before", value=before.content or "*no content*", inline=False)
        embed.add_field(name="after", value=after.content or "*no content*", inline=False)
        embed.set_footer(text=f"user id: {before.author.id}")
        await log_channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageLogging(bot))
