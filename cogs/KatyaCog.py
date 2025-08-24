import discord
from discord.ext import commands
from discord import app_commands

class KatyaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Accent color for embeds
        raw_color = bot.config.get("accent", "#ff8040")
        if isinstance(raw_color, str):
            self.accent = int(raw_color.lstrip("#"), 16)
        else:
            self.accent = int(raw_color)

        raw_color = bot.config.get("error_accent", "#ff8040")
        if isinstance(raw_color, str):
            self.error_accent = int(raw_color.lstrip("#"), 16)
        else:
            self.error_accent = int(raw_color)
            
        self.emoji = bot.config.get("emoji", "🧡")
        self.error = bot.config.get("error", "🧡")

    def parse_emojis(self, text: str) -> str:
        for name, emoji in self.custom_emojis.items():
            text = text.replace(f"{{{name}}}", emoji)
        return text
        
    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=f"{self.error} {title}",
            description=description,
            color=self.error_accent
        )
