import discord
from discord import app_commands
from discord.ext import commands


class Introduction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="introduction", description="Introduce Eden to the server.")
    async def introduction(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            description=(
                "hey!! i'm eden 🌱 the server's bot, here to keep things running smoothly "
                "(and occasionally cause chaos)\n\n"
                "i can help you grab roles, get verified, and the mods can use me to keep "
                "an eye on things behind the scenes\n\n"
                "be gay do crimes 🏳️‍⚧️"
            ),
            color=discord.Color.green(),
        )

        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Introduction(bot))
