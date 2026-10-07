import asyncio
import logging
import os
import re

import discord
from discord import app_commands
from discord.ext import commands, tasks

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


def _get_restart_interval() -> int:
    raw = os.getenv("AUTO_RESTART_HOURS", "48")
    return int(raw) if raw.isdigit() else 48


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._restart_loop_running = False
        self.auto_restart.start()

    def cog_unload(self) -> None:
        self.auto_restart.cancel()

    @tasks.loop(hours=1)
    async def auto_restart(self) -> None:
        interval = _get_restart_interval()
        if interval == 0:
            return
        started_at = getattr(self.bot, "started_at", None)
        if started_at is None:
            return
        elapsed_hours = (discord.utils.utcnow() - started_at).total_seconds() / 3600
        if elapsed_hours >= interval:
            self.logger.info("Automatic restart triggered after %d hours", interval)
            os._exit(1)

    @auto_restart.before_loop
    async def before_auto_restart(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="set_restart_interval", description="Set the automatic restart interval in hours (0 to disable).")
    @app_commands.describe(hours="Hours between automatic restarts. Set to 0 to disable.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_restart_interval(self, interaction: discord.Interaction, hours: int) -> None:
        if hours < 0:
            await interaction.response.send_message("Hours must be 0 or greater.", ephemeral=True)
            return
        _write_env_var("AUTO_RESTART_HOURS", str(hours))
        if hours == 0:
            description = "automatic restarts are now **disabled**."
        else:
            description = f"bot will automatically restart every **{hours} hours**."
        embed = discord.Embed(
            title="✅ restart interval updated",
            description=description,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=stamp(embed, self.bot), ephemeral=True)

    @app_commands.command(name="restart", description="Restart the bot and pull latest code.")
    @app_commands.default_permissions(manage_guild=True)
    async def restart(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🔄 restarting...",
            description="pulling latest code and coming right back 🌱",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=stamp(embed, self.bot), ephemeral=True)
        self.logger.info("Restart requested by %s", interaction.user)
        await asyncio.sleep(0.5)
        os._exit(1)

    @commands.command(name="forward")
    @commands.has_permissions(manage_messages=True)
    async def forward(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Reply to a message with !forward <channel> to forward it verbatim to that channel."""
        if ctx.message.reference is None:
            await ctx.send("You need to reply to a message to forward it.", delete_after=5)
            return

        ref = ctx.message.reference
        source: discord.Message | None = ref.resolved if isinstance(ref.resolved, discord.Message) else None
        if source is None:
            try:
                source = await ctx.channel.fetch_message(ref.message_id)
            except discord.NotFound:
                await ctx.send("Could not find the message you replied to.", delete_after=5)
                return

        files: list[discord.File] = []
        for attachment in source.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        await channel.send(
            content=source.content or None,
            embeds=source.embeds[:10],
            files=files,
        )

        confirm = discord.Embed(
            description=f"Message forwarded to {channel.mention}.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=stamp(confirm, self.bot), delete_after=5)

    @forward.error
    async def forward_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the **Manage Messages** permission to use this command.", delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Could not find that channel. Pass a channel mention or valid channel ID.", delete_after=5)
        else:
            self.logger.exception("Error in forward command", exc_info=error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
