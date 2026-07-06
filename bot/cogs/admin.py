import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @app_commands.command(name="restart", description="Restart the bot and pull latest code.")
    @app_commands.default_permissions(manage_guild=True)
    async def restart(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Restarting...", ephemeral=True)
        self.logger.info("Restart requested by %s", interaction.user)
        await self.bot.close()
        os._exit(0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
