import discord
from discord import app_commands
from discord.ext import commands, tasks

STAT_CHOICES = [
    app_commands.Choice(name="Total Members", value="total"),
    app_commands.Choice(name="Online Members", value="online"),
    app_commands.Choice(name="Bot Count", value="bots"),
    app_commands.Choice(name="Human Members", value="humans"),
]

STAT_LABELS = {
    "total": "👥 Members",
    "online": "🟢 Online",
    "bots": "🤖 Bots",
    "humans": "👤 Humans",
}


def _count(guild: discord.Guild, stat: str) -> int:
    if stat == "total":
        return guild.member_count or len(guild.members)
    if stat == "online":
        return sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
    if stat == "bots":
        return sum(1 for m in guild.members if m.bot)
    if stat == "humans":
        return sum(1 for m in guild.members if not m.bot)
    return 0


class ServerStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._channels: dict[int, str] = {}  # channel_id -> stat key
        self.update_task.start()

    def cog_unload(self) -> None:
        self.update_task.cancel()

    async def _load(self) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stat_channels (
                    channel_id BIGINT PRIMARY KEY,
                    stat       TEXT NOT NULL
                )
                """
            )
            rows = await conn.fetch("SELECT channel_id, stat FROM stat_channels")
        self._channels = {r["channel_id"]: r["stat"] for r in rows}

    async def _save(self, channel_id: int, stat: str) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO stat_channels (channel_id, stat)
                VALUES ($1, $2)
                ON CONFLICT (channel_id) DO UPDATE SET stat = EXCLUDED.stat
                """,
                channel_id,
                stat,
            )

    async def _delete(self, channel_id: int) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM stat_channels WHERE channel_id = $1", channel_id)

    async def _refresh_all(self) -> None:
        for channel_id, stat in list(self._channels.items()):
            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                continue
            guild = channel.guild
            label = STAT_LABELS.get(stat, stat)
            count = _count(guild, stat)
            new_name = f"{label}: {count}"
            if channel.name != new_name:
                try:
                    await channel.edit(name=new_name, reason="server stats update")
                except discord.HTTPException:
                    pass

    @tasks.loop(minutes=10)
    async def update_task(self) -> None:
        await self._refresh_all()

    @update_task.before_loop
    async def before_update_task(self) -> None:
        await self.bot.wait_until_ready()
        await self._load()
        await self._refresh_all()

    @app_commands.command(name="setup_stats", description="Link a voice channel to a live server stat.")
    @app_commands.describe(channel="Voice channel to use as a stat display", stat="Which stat to show")
    @app_commands.choices(stat=STAT_CHOICES)
    @app_commands.default_permissions(manage_guild=True)
    async def setup_stats(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        stat: app_commands.Choice[str],
    ) -> None:
        self._channels[channel.id] = stat.value
        await self._save(channel.id, stat.value)

        label = STAT_LABELS.get(stat.value, stat.value)
        guild = interaction.guild
        count = _count(guild, stat.value) if guild else "?"
        new_name = f"{label}: {count}"
        try:
            await channel.edit(name=new_name, reason="server stats setup")
        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="✅ stat channel configured",
            description=f"{channel.mention} will now show **{stat.name}** and update every 10 minutes.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remove_stats", description="Stop tracking a stat in a voice channel.")
    @app_commands.describe(channel="Voice channel to stop updating")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_stats(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
    ) -> None:
        if channel.id not in self._channels:
            await interaction.response.send_message(
                "That channel isn't being tracked.", ephemeral=True
            )
            return

        del self._channels[channel.id]
        await self._delete(channel.id)

        embed = discord.Embed(
            title="🗑️ stat channel removed",
            description=f"{channel.mention} will no longer be updated.",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="list_stats", description="Show all active stat channels.")
    @app_commands.default_permissions(manage_guild=True)
    async def list_stats(self, interaction: discord.Interaction) -> None:
        if not self._channels:
            await interaction.response.send_message("No stat channels configured.", ephemeral=True)
            return

        lines = []
        for channel_id, stat in self._channels.items():
            channel = self.bot.get_channel(channel_id)
            mention = channel.mention if channel else f"<#{channel_id}> *(deleted?)*"
            lines.append(f"{mention} → **{STAT_LABELS.get(stat, stat)}**")

        embed = discord.Embed(
            title="📊 stat channels",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStats(bot))
