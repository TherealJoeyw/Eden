import discord
from discord import app_commands
from discord.ext import commands

from ._utils import stamp

def _tier(percentile: float) -> str:
    """percentile is 0-100, where 100 = most active on the server."""
    if percentile >= 90:
        return "🔥 very active"
    if percentile >= 60:
        return "🟢 active"
    if percentile >= 25:
        return "🟡 moderate"
    return "🔴 quiet"


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_table(self) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity (
                    user_id     BIGINT PRIMARY KEY,
                    total_msgs  BIGINT NOT NULL DEFAULT 0,
                    last_active TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS activity_daily (
                    user_id BIGINT  NOT NULL,
                    day     DATE    NOT NULL,
                    msgs    INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, day)
                );
                """
            )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._ensure_table()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            return
        uid = message.author.id
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity (user_id, total_msgs, last_active)
                VALUES ($1, 1, now())
                ON CONFLICT (user_id) DO UPDATE
                    SET total_msgs  = activity.total_msgs + 1,
                        last_active = now()
                """,
                uid,
            )
            await conn.execute(
                """
                INSERT INTO activity_daily (user_id, day, msgs)
                VALUES ($1, current_date, 1)
                ON CONFLICT (user_id, day) DO UPDATE
                    SET msgs = activity_daily.msgs + 1
                """,
                uid,
            )

    @app_commands.command(name="activity", description="Show activity stats for a member.")
    @app_commands.default_permissions(manage_guild=True)
    async def activity(self, interaction: discord.Interaction, member: discord.Member) -> None:
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            await interaction.response.send_message("Database unavailable.", ephemeral=True)
            return

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT total_msgs, last_active FROM activity WHERE user_id = $1", member.id
            )
            week = await conn.fetchval(
                """
                SELECT COALESCE(SUM(msgs), 0)
                FROM activity_daily
                WHERE user_id = $1 AND day >= current_date - INTERVAL '6 days'
                """,
                member.id,
            )
            percentile = await conn.fetchval(
                """
                WITH totals AS (
                    SELECT user_id, SUM(msgs) AS week_msgs
                    FROM activity_daily
                    WHERE day >= current_date - INTERVAL '6 days'
                    GROUP BY user_id
                )
                SELECT ROUND(
                    100.0 * (SELECT COUNT(*) FROM totals WHERE week_msgs <= $2)
                    / NULLIF((SELECT COUNT(*) FROM totals), 0)
                , 1)
                """,
                member.id,
                week or 0,
            )

        total = row["total_msgs"] if row else 0
        last_active = row["last_active"] if row else None
        daily_avg = (week or 0) / 7
        pct = float(percentile or 0)

        embed = discord.Embed(title=f"📊 activity — {member.display_name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="tier", value=_tier(pct), inline=True)
        embed.add_field(name="server percentile", value=f"top {100 - pct:.0f}%", inline=True)
        embed.add_field(name="7d avg", value=f"{daily_avg:.1f} msgs/day", inline=True)
        embed.add_field(name="7d total", value=f"{week or 0} msgs", inline=True)
        embed.add_field(name="all time", value=f"{total} msgs", inline=True)
        embed.add_field(
            name="last active",
            value=discord.utils.format_dt(last_active, "R") if last_active else "never recorded",
            inline=True,
        )
        embed.add_field(
            name="joined server",
            value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "unknown",
            inline=True,
        )
        embed.add_field(
            name="account age",
            value=discord.utils.format_dt(member.created_at, "R"),
            inline=True,
        )
        await interaction.response.send_message(embed=stamp(embed, self.bot), ephemeral=True)

    @app_commands.command(name="topmembers", description="Show the most active members over the last 7 days.")
    @app_commands.describe(limit="Number of members to show (default 10, max 25)")
    @app_commands.default_permissions(manage_guild=True)
    async def topmembers(self, interaction: discord.Interaction, limit: int = 10) -> None:
        limit = max(1, min(limit, 25))
        pool = getattr(self.bot, "db_pool", None)
        if pool is None:
            await interaction.response.send_message("Database unavailable.", ephemeral=True)
            return

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, COALESCE(SUM(msgs), 0) AS week_msgs
                FROM activity_daily
                WHERE day >= current_date - INTERVAL '6 days'
                GROUP BY user_id
                ORDER BY week_msgs DESC
                LIMIT $1
                """,
                limit,
            )

        if not rows:
            await interaction.response.send_message("No activity recorded yet.", ephemeral=True)
            return

        total_users = len(rows)
        lines = []
        for i, row in enumerate(rows, 1):
            member = interaction.guild.get_member(row["user_id"]) if interaction.guild else None
            name = member.display_name if member else f"<@{row['user_id']}>"
            daily_avg = row["week_msgs"] / 7
            # rank 1 = top, so percentile = 100 - ((i-1)/total * 100)
            pct = 100 - ((i - 1) / total_users * 100)
            lines.append(f"`{i}.` {name} — {row['week_msgs']} msgs ({daily_avg:.1f}/day) {_tier(pct)}")

        embed = discord.Embed(
            title="📊 most active members — last 7 days",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=stamp(embed, self.bot), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Activity(bot))
