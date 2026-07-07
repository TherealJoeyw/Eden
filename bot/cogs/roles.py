import os
import re

import discord
from discord import app_commands
from discord.ext import commands

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


def _get_saved_role_ids() -> set[int]:
    raw = os.getenv("ROLE_PANEL_IDS", "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


def _save_role_ids(roles: list[discord.Role]) -> None:
    _write_env_var("ROLE_PANEL_IDS", ",".join(str(r.id) for r in roles[:25]))


class RoleSelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role], *, role_ids: set[int] | None = None):
        if roles:
            options = [
                discord.SelectOption(label=role.name, value=str(role.id))
                for role in roles[:25]
            ]
            self.assignable_role_ids = {role.id for role in roles[:25]}
        else:
            saved = role_ids or set()
            options = [discord.SelectOption(label=str(rid), value=str(rid)) for rid in saved]
            self.assignable_role_ids = saved

        if not options:
            options = [discord.SelectOption(label="No roles available", value="__no_roles__")]

        super().__init__(
            placeholder="Select roles to assign",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="role_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Could not identify member.", ephemeral=True)
            return

        selected_ids = {int(role_id) for role_id in self.values if role_id.isdigit()}
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
    def __init__(self, roles: list[discord.Role], *, role_ids: set[int] | None = None):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(roles, role_ids=role_ids))

    @classmethod
    def from_ids(cls, role_ids: set[int]) -> "RoleSelectView":
        return cls([], role_ids=role_ids)


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(RoleSelectView.from_ids(_get_saved_role_ids()))

    @app_commands.command(name="roles_panel", description="Post a self-assign roles panel with chosen roles.")
    @app_commands.describe(
        title="Label shown above the dropdown",
        role1="Role to include", role2="Role to include", role3="Role to include",
        role4="Role to include", role5="Role to include", role6="Role to include",
        role7="Role to include", role8="Role to include", role9="Role to include",
        role10="Role to include",
    )
    @app_commands.default_permissions(manage_roles=True)
    async def roles_panel(
        self,
        interaction: discord.Interaction,
        role1: discord.Role,
        role2: discord.Role | None = None,
        role3: discord.Role | None = None,
        role4: discord.Role | None = None,
        role5: discord.Role | None = None,
        role6: discord.Role | None = None,
        role7: discord.Role | None = None,
        role8: discord.Role | None = None,
        role9: discord.Role | None = None,
        role10: discord.Role | None = None,
        title: str = "Choose your roles from the dropdown below:",
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        roles = [r for r in [role1, role2, role3, role4, role5, role6, role7, role8, role9, role10] if r is not None]

        bot_member = guild.me
        invalid = [r for r in roles if bot_member and r >= bot_member.top_role]
        if invalid:
            names = ", ".join(r.mention for r in invalid)
            await interaction.response.send_message(
                f"These roles are above my highest role and can't be assigned: {names}",
                ephemeral=True,
            )
            return

        _save_role_ids(roles)
        view = RoleSelectView(roles)
        await interaction.channel.send(title, view=view)
        await interaction.response.send_message("✅ roles panel posted.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))
