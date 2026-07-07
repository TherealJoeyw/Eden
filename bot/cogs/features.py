import discord
from discord import app_commands
from discord.ext import commands

from ._utils import stamp

FEATURES = {
    "🎫 verification": [
        "`/verification_panel` — post a ticket panel for new members",
    ],
    "🎭 roles": [
        "`/roles_panel` — post a self-assignable role selector",
    ],
    "📊 server stats": [
        "`/setup_stats` — link a voice channel to a live stat",
        "`/remove_stats` — stop updating a stat channel",
        "`/list_stats` — view all active stat channels",
    ],
    "📝 logging": [
        "`/set_log_channel` — set where message edits/deletes are logged",
    ],
    "🚨 reports": [
        "right-click any message → **Apps → Report Message**",
        "`/report <message_id>` — report by message ID",
        "`/set_report_channel` — set where reports are sent",
        "`/set_report_ping_role` — set the role pinged on new reports",
    ],
    "💾 backups": [
        "`/backup` — trigger a manual database backup",
        "`/restore` — restore from a backup file",
        "`/listbackups` — list available backups",
    ],
    "🔧 admin": [
        "`/restart` — restart the bot",
        "`/diagnostics` — view bot health info",
    ],
    "👋 misc": [
        "`/introduction` — post a server introduction embed",
        "mention the bot — get a pong 🏓",
    ],
}


class Features(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="features", description="Show all of Eden's features and commands.")
    async def features(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🌱 eden — features",
            description="here's everything i can do:",
            color=discord.Color.green(),
        )
        for category, commands_list in FEATURES.items():
            embed.add_field(
                name=category,
                value="\n".join(commands_list),
                inline=False,
            )
        await interaction.response.send_message(embed=stamp(embed, self.bot))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Features(bot))
