import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands


class Diagnostics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="diagnostics", description="Show bot diagnostics.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def diagnostics(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000, 2)

        db_status = "Unavailable"
        db_pool = getattr(self.bot, "db_pool", None)
        if db_pool is not None:
            try:
                async with db_pool.acquire() as connection:
                    result = await connection.fetchval("SELECT 1")
                db_status = "Connected" if result == 1 else "Unexpected response"
            except Exception:
                db_status = "Disconnected"

        command_count = sum(1 for _ in self.bot.tree.walk_commands())
        cog_count = len(self.bot.cogs)

        uptime = "Unknown"
        started_at = getattr(self.bot, "started_at", None)
        if started_at is not None:
            elapsed = discord.utils.utcnow() - started_at
            uptime = str(timedelta(seconds=int(elapsed.total_seconds())))

        embed = discord.Embed(title="Diagnostics", color=discord.Color.blurple())
        embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=False)
        embed.add_field(name="Database", value=db_status, inline=False)
        embed.add_field(name="Loaded cogs", value=str(cog_count), inline=False)
        embed.add_field(name="Slash commands", value=str(command_count), inline=False)
        embed.add_field(name="Uptime", value=uptime, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Diagnostics(bot))
