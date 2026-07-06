import discord
from discord import app_commands
from discord.ext import commands


class MessageLogging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        if getattr(self.bot, "db_pool", None) is None:
            return
        async with self.bot.db_pool.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_logging_settings (
                    guild_id BIGINT PRIMARY KEY,
                    log_channel_id BIGINT NOT NULL
                )
                """
            )

    async def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if getattr(self.bot, "db_pool", None) is None:
            return None
        async with self.bot.db_pool.acquire() as connection:
            record = await connection.fetchrow(
                "SELECT log_channel_id FROM guild_logging_settings WHERE guild_id = $1",
                guild.id,
            )
        if not record:
            return None
        channel = guild.get_channel(record["log_channel_id"])
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @app_commands.command(name="set_log_channel", description="Set the channel used for message logs.")
    @app_commands.default_permissions(manage_guild=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        if getattr(self.bot, "db_pool", None) is None:
            await interaction.response.send_message("Database pool is unavailable.", ephemeral=True)
            return

        async with self.bot.db_pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO guild_logging_settings (guild_id, log_channel_id)
                VALUES ($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE SET log_channel_id = EXCLUDED.log_channel_id
                """,
                guild.id,
                channel.id,
            )
        await interaction.response.send_message(
            f"Log channel set to {channel.mention}.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        log_channel = await self._get_log_channel(message.guild)
        if log_channel is None:
            return

        embed = discord.Embed(title="Message Deleted", color=discord.Color.red())
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content or "*No content*", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return

        log_channel = await self._get_log_channel(before.guild)
        if log_channel is None:
            return

        embed = discord.Embed(title="Message Edited", color=discord.Color.orange())
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content or "*No content*", inline=False)
        embed.add_field(name="After", value=after.content or "*No content*", inline=False)
        await log_channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageLogging(bot))
