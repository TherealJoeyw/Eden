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


def _get_report_channel_id() -> int | None:
    raw = os.getenv("REPORT_CHANNEL_ID")
    if raw and raw.isdigit():
        return int(raw)
    return None


def _get_report_ping_role_id() -> int | None:
    raw = os.getenv("REPORT_PING_ROLE_ID")
    if raw and raw.isdigit():
        return int(raw)
    return None


async def _send_report(
    bot: commands.Bot,
    reporter: discord.Member,
    message: discord.Message,
    reason: str | None,
) -> bool:
    channel_id = _get_report_channel_id()
    if channel_id is None:
        return False
    channel = bot.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return False

    embed = discord.Embed(title="🚨 message reported", color=discord.Color.red())
    embed.add_field(name="📢 reported by", value=reporter.mention, inline=True)
    embed.add_field(name="👤 author", value=message.author.mention, inline=True)
    embed.add_field(name="📍 channel", value=message.channel.mention, inline=True)
    embed.add_field(name="🔗 jump to message", value=f"[click here]({message.jump_url})", inline=False)
    if message.content:
        embed.add_field(name="💬 content", value=message.content[:1024], inline=False)
    if reason:
        embed.add_field(name="📝 reason", value=reason, inline=False)
    if message.attachments:
        names = "\n".join(f"`{a.filename}`" for a in message.attachments)
        embed.add_field(name="📎 attachments", value=names, inline=False)
    embed.set_footer(text=f"reporter id: {reporter.id} · author id: {message.author.id}")

    ping = None
    role_id = _get_report_ping_role_id()
    if role_id:
        ping = f"<@&{role_id}>"

    await channel.send(content=ping, embed=stamp(embed, bot))
    return True


class ReportModal(discord.ui.Modal, title="Report Message"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="What's wrong with this message?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, message: discord.Message):
        super().__init__()
        self.target_message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        sent = await _send_report(
            interaction.client,
            interaction.user,
            self.target_message,
            self.reason.value or None,
        )

        if sent:
            await interaction.response.send_message(
                "✅ your report has been submitted. thank you.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ no report channel is configured. ask an admin to run `/set_report_channel`.",
                ephemeral=True,
            )


class Reports(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # register context menu
        self._ctx_menu = app_commands.ContextMenu(
            name="Report Message",
            callback=self.report_context_menu,
        )
        self.bot.tree.add_command(self._ctx_menu)

    def cog_unload(self) -> None:
        self.bot.tree.remove_command(self._ctx_menu.name, type=self._ctx_menu.type)

    async def report_context_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        if message.author == interaction.user:
            await interaction.response.send_message("You can't report your own message.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportModal(message))

    @app_commands.command(name="report", description="Report a message by ID.")
    @app_commands.describe(message_id="ID of the message to report", reason="Why are you reporting this?")
    async def report(
        self,
        interaction: discord.Interaction,
        message_id: str,
        reason: str | None = None,
    ) -> None:
        if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Use this command in a text channel.", ephemeral=True)
            return
        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except (discord.NotFound, ValueError):
            await interaction.response.send_message("Message not found in this channel.", ephemeral=True)
            return
        if message.author == interaction.user:
            await interaction.response.send_message("You can't report your own message.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        sent = await _send_report(interaction.client, interaction.user, message, reason)
        if sent:
            await interaction.response.send_message("✅ your report has been submitted. thank you.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "⚠️ no report channel is configured. ask an admin to run `/set_report_channel`.",
                ephemeral=True,
            )

    @app_commands.command(name="set_report_channel", description="Set the channel where reports are sent.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_report_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        _write_env_var("REPORT_CHANNEL_ID", str(channel.id))
        embed = discord.Embed(
            title="✅ report channel set",
            description=f"reports will now be sent to {channel.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_report_ping_role", description="Set the role to ping when a report is submitted.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_report_ping_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        _write_env_var("REPORT_PING_ROLE_ID", str(role.id))
        embed = discord.Embed(
            title="✅ report ping role set",
            description=f"{role.mention} will be pinged on every new report.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reports(bot))
