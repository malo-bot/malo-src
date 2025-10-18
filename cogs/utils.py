# utils.py
import time
import random
import io
from datetime import datetime
import asyncio
import yaml
from PIL import Image, UnidentifiedImageError
import pytesseract
from discord.ext import commands
from discord import app_commands
import discord
from helper import secondsightify, tofullwidth, italicize, italicize_random
from .KatyaCog import KatyaCog
from serpapi import GoogleSearch
from googletrans import Translator

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
serp_key = config["serp_key"]

class Utils(KatyaCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

        self.ocr_message_ctx = app_commands.ContextMenu(
            name="OCR Image",
            callback=self.ocr_message,
        )
        self.ocr_message_ctx.allowed_installs = app_commands.AppInstallationType(guild=True, user=True)
        self.ocr_message_ctx.allowed_contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        bot.tree.add_command(self.ocr_message_ctx)

        self.translate_ctx = app_commands.ContextMenu(
            name="Translate",
            callback=self.translate,
        )
        self.translate_ctx.allowed_installs = app_commands.AppInstallationType(guild=True, user=True)
        self.translate_ctx.allowed_contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        bot.tree.add_command(self.translate_ctx)

        self.utils_group = app_commands.Group(name="utils", description="Utility commands")
        bot.tree.add_command(self.utils_group)

        self.utils_group.command(name="roll", description="Roll a dice")(self.roll)
        self.utils_group.command(
            name="eye",
            description="3y3 - credits to Twilight Sparkle (@yourcompanionAI)!"
        )(self.secondsightify_slash)
        self.utils_group.command(name="fullwidth", description="Convert text to fullwidth")(self.fullwidth)
        self.utils_group.command(name="translate", description="Translate text into English")(self.translate_cmd)
        self.utils_group.command(name="ocr", description="Read / extract text from an image.")(self.readtext)
        self.utils_group.command(name="lens", description="Reverse image search")(self.lens)

    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, sides)
        embed = self.create_simple_embed("Dice Result:", f"You rolled a {result}")
        await interaction.response.send_message(embed=embed)

    async def secondsightify_slash(self, interaction: discord.Interaction, text: str):
        result, concealed = secondsightify(text)
        if concealed:
            result += "\n\n👆 Copy this!"
        embed = self.create_simple_embed("Eye Result:", result)
        await interaction.response.send_message(embed=embed)

    async def fullwidth(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(thinking=True)
        result = tofullwidth(text)
        MAX_DESC_LEN = 3250
        truncated_result = result[:MAX_DESC_LEN] + "..." if len(result) > MAX_DESC_LEN else result
        final = "`" + truncated_result + "`"
        embed = self.create_simple_embed("Result:", final)
        await interaction.followup.send(embed=embed)

    async def translate_cmd(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()
        translator = Translator()
        try:
            result = await translator.translate(text, src="auto", dest="en")
            embed = self.create_simple_embed(f"Translated `{result.src}` → `en`", result.text)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = self.create_error_embed("Translation Error", str(e))
            await interaction.followup.send(embed=embed)

    async def readtext(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer()
        if not image.content_type or not image.content_type.startswith("image/"):
            embed = self.create_error_embed("Invalid file", "Please upload a valid image file.")
            await interaction.followup.send(embed=embed)
            return
        try:
            image_bytes = await image.read()
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img).strip() or "No text found in the image."
            embed = self.create_simple_embed("OCR Result:", text)
        except UnidentifiedImageError:
            embed = self.create_error_embed("Unsupported format", f"Cannot read image format `{image.content_type}`")
        except Exception as e:
            embed = self.create_error_embed("OCR Failed", str(e))
        await interaction.followup.send(embed=embed)

    async def lens(self, interaction: discord.Interaction, image: discord.Attachment):
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True)
        embed = discord.Embed(title="Google Lens Results", colour=self.accent, timestamp=datetime.now())
        embed.set_footer(text=self.emoji)
        params = {
            "engine": "google_lens",
            "url": image.url,
            "api_key": serp_key,
            "type": "all",
            "safe": "off"
        }
        try:
            results = await asyncio.to_thread(lambda: GoogleSearch(params).get_dict())
        except Exception as e:
            error_embed = self.create_error_embed("Reverse image search failed", f"{type(e).__name__}: {e}")
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        if "error" in results:
            error_msg = results.get("error", "Unknown API error.")
            if "quota" in error_msg.lower() or "limit" in error_msg.lower():
                friendly_msg = "You’ve hit the SerpAPI quota. Please try again later."
            elif "invalid api key" in error_msg.lower():
                friendly_msg = "The API key is invalid."
            else:
                friendly_msg = error_msg
            error_embed = self.create_error_embed("Reverse image search failed", friendly_msg)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        visual_matches = results.get("visual_matches", [])
        related_content = results.get("related_content", [])

        if related_content:
            related_links = "\n".join(f"[{r.get('query','No query')}]({r.get('link','')})" for r in related_content[:8])
            embed.add_field(name="Related Content", value=related_links or "No related links", inline=False)

        if not visual_matches:
            error_embed = self.create_error_embed("Reverse image search failed", "No visual matches found.")
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        first_thumb = visual_matches[0].get("thumbnail")
        if first_thumb:
            embed.set_thumbnail(url=first_thumb)

        for match in visual_matches[:8]:
            embed.add_field(name=match.get("title", "No title"), value=match.get("link", "No link"), inline=False)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        embed.set_footer(text=f"{self.emoji} • Took {elapsed_ms}ms")
        await interaction.followup.send(embed=embed)

    # ---- Context Menu Handlers ----
    async def ocr_message(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            embed = self.create_error_embed("No attachments", "Message has no attachments.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await self.readtext(interaction, message.attachments[0])

    async def translate(self, interaction: discord.Interaction, message: discord.Message):
        if not message.content:
            embed = self.create_error_embed("Translation Error", "This message has no usable content.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await self.translate_cmd(interaction, message.content)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))
