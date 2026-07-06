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
        latency_emoji = "🟢" if latency_ms < 100 else "🟡" if latency_ms < 200 else "🔴"

        db_status = "⚪ Unavailable"
        db_pool = getattr(self.bot, "db_pool", None)
        if db_pool is not None:
            try:
                async with db_pool.acquire() as connection:
                    result = await connection.fetchval("SELECT 1")
                db_status = "🟢 Connected" if result == 1 else "🟡 Unexpected response"
            except Exception:
                db_status = "🔴 Disconnected"

        command_count = sum(1 for _ in self.bot.tree.walk_commands())
        cog_count = len(self.bot.cogs)

        uptime = "Unknown"
        started_at = getattr(self.bot, "started_at", None)
        if started_at is not None:
            elapsed = discord.utils.utcnow() - started_at
            uptime = str(timedelta(seconds=int(elapsed.total_seconds())))

        embed = discord.Embed(title="🌱 eden — diagnostics", color=discord.Color.green())
        embed.add_field(name="📡 latency", value=f"{latency_emoji} {latency_ms} ms", inline=True)
        embed.add_field(name="🗄️ database", value=db_status, inline=True)
        embed.add_field(name="⏱️ uptime", value=f"`{uptime}`", inline=True)
        embed.add_field(name="🧩 cogs loaded", value=str(cog_count), inline=True)
        embed.add_field(name="⚡ commands", value=str(command_count), inline=True)

        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Diagnostics(bot))
