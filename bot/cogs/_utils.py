import discord
from discord.ext import commands


def stamp(embed: discord.Embed, bot: commands.Bot) -> discord.Embed:
    instance_id = getattr(bot, "instance_id", "????")
    existing = embed.footer.text or ""
    separator = " · " if existing else ""
    embed.set_footer(text=f"{existing}{separator}#{instance_id}")
    return embed
