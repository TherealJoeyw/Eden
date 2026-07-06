import discord
from discord import app_commands
from discord.ext import commands


class RoleSelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role]):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in roles[:25]
        ]
        super().__init__(
            placeholder="Select roles to assign",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self.assignable_role_ids = {role.id for role in roles[:25]}

    async def callback(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Could not identify member.", ephemeral=True)
            return

        selected_ids = {int(role_id) for role_id in self.values}
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        assignable_roles = [
            guild.get_role(role_id)
            for role_id in self.assignable_role_ids
            if guild.get_role(role_id) is not None
        ]
        to_add = [role for role in assignable_roles if role.id in selected_ids and role not in member.roles]
        to_remove = [role for role in assignable_roles if role.id not in selected_ids and role in member.roles]

        if to_add:
            await member.add_roles(*to_add, reason="Self-assigned role selection")
        if to_remove:
            await member.remove_roles(*to_remove, reason="Self-assigned role selection update")

        await interaction.response.send_message("Your roles have been updated.", ephemeral=True)


class RoleSelectView(discord.ui.View):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(roles))


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roles_panel", description="Post a self-assign roles panel.")
    @app_commands.default_permissions(manage_roles=True)
    async def roles_panel(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        member = guild.me
        if member is None:
            await interaction.response.send_message("Bot member state unavailable.", ephemeral=True)
            return

        available_roles = [
            role
            for role in guild.roles
            if not role.is_default()
            and not role.managed
            and role < member.top_role
        ]
        available_roles.reverse()

        if not available_roles:
            await interaction.response.send_message(
                "No assignable roles found below my highest role.",
                ephemeral=True,
            )
            return

        view = RoleSelectView(available_roles)
        await interaction.channel.send(
            "Choose your roles from the dropdown below:",
            view=view,
        )
        await interaction.response.send_message("Roles panel posted.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))
