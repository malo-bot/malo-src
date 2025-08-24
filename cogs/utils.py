import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import random
from helper import secondsightify, tofullwidth, italicize, italicize_random
from .KatyaCog import KatyaCog

class Utils(KatyaCog):  # inherit instead of commands.Cog
    utils = app_commands.Group(name="utils", description="Utility commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)  # initialize base cog

    utils = app_commands.Group(name="utils", description="Utility commands")

    @utils.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, sides)
        embed = discord.Embed(
            title=f"You rolled a {result}! 🎲",
            colour=self.accent,
            timestamp=datetime.now()
        )
        embed.set_author(name="Result:")
        embed.set_footer(text=self.emoji)
        await interaction.response.send_message(embed=embed)

    @utils.command(
        name="secondsightify",
        description="3y3 / eye - credits to Twilight Sparkle (@yourcompanionAI)!"
    )
    async def secondsightify_slash(self, interaction: discord.Interaction, text: str):
        result, concealed = secondsightify(text)

        embed = discord.Embed(
            title="Result:",
            description=result,
            colour=self.accent,
            timestamp=datetime.now()
        )
        embed.set_footer(text=self.emoji)

        if concealed:
            embed.description = result + "\n\n👆 Copy this!"

        await interaction.response.send_message(embed=embed)

    @utils.command(name="fullwidth", description="Convert text to fullwidth")
    async def fullwidth(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(thinking=True)

        result = tofullwidth(text)

        MAX_DESC_LEN = 3250
        if len(result) > MAX_DESC_LEN:
            truncated_result = result[:MAX_DESC_LEN] + "..."
        else:
            truncated_result = result
        final = "`" + truncated_result + "`"
        embed = discord.Embed(
            title="Result:",
            description=final,
            colour=self.accent,
            timestamp=datetime.now()
        )
        embed.set_footer(text=self.emoji)

        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))
