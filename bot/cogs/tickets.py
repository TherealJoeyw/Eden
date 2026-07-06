import discord
from discord import app_commands
from discord.ext import commands

from ._utils import stamp


class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button", emoji="🔒")

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if channel is None:
            await interaction.response.send_message("Channel not found.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 closing ticket...", ephemeral=True)
        await channel.delete(reason=f"Ticket closed by {interaction.user}")


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())





class OpenTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Open Verification Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_button", emoji="🎫")

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        user = interaction.user
        if guild is None or not isinstance(user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        channel_name = f"verify-{user.id}"
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing is not None:
            await interaction.response.send_message(
                f"🎫 you already have an open ticket: {existing.mention}",
                ephemeral=True,
            )
            return

        category = discord.utils.get(guild.categories, name="Verification Tickets")
        if category is None:
            category = await guild.create_category("Verification Tickets", reason="Ticket setup")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Verification ticket for {user}",
        )

        embed = discord.Embed(
            title="🌱 verification ticket",
            description=f"hey {user.mention}! thanks for opening a ticket 💚\nstaff will be with you shortly, hang tight!",
            color=discord.Color.green(),
        )
        await ticket_channel.send(embed=stamp(embed, interaction.client), view=CloseTicketView())
        await interaction.response.send_message(
            f"🎫 ticket created: {ticket_channel.mention}",
            ephemeral=True,
        )


class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(OpenTicketButton())


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="verification_panel", description="Post the verification ticket panel.")
    @app_commands.default_permissions(manage_channels=True)
    async def verification_panel(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🌱 need help getting verified?",
            description="click the button below to open a private ticket and a staff member will assist you!",
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=stamp(embed, self.bot), view=OpenTicketView())
        await interaction.response.send_message("✅ verification panel posted!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
