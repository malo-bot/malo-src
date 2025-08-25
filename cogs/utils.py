# pip install google-search-results
import discord
from discord.ext import commands
from discord import app_commands
import random
from helper import secondsightify, tofullwidth, italicize, italicize_random
from .KatyaCog import KatyaCog
import yaml
from serpapi import GoogleSearch
from googletrans import Translator
from PIL import Image, UnidentifiedImageError
import pytesseract
import io
import asyncio
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
serp_key = config["serp_key"]

class Utils(KatyaCog):  # inherit instead of commands.Cog
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)  # initialize base cog

        self.ocr_message_ctx = app_commands.ContextMenu(
            name="OCR Image",
            callback=self.ocr_message,
        )
        
        self.ocr_message_ctx.allowed_installs = app_commands.AppInstallationType(guild=True, user=True)
        self.ocr_message_ctx.allowed_contexts = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
        
        bot.tree.add_command(self.ocr_message_ctx)
        
        self.translate_ctx = app_commands.ContextMenu(
            name="Translate",
            callback=self.translate,
        )

        # Optional restrictions
        self.translate_ctx.allowed_installs = app_commands.AppInstallationType(
            guild=True, user=True
        )
        self.translate_ctx.allowed_contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )

        bot.tree.add_command(self.translate_ctx)

    async def translate(
        self,
        interaction: discord.Interaction,
        message: discord.Message
    ):
        if not message.content:
            embed = self.create_error_embed(
                "Translation Error",
                "This message has no usable content."
            )
            await interaction.response.send_message(embed=embed,ephemeral=True)
            return
        await interaction.response.defer()
        translator = Translator()
        try:
            result = await translator.translate(message.content, src="auto", dest="en")
            embed = self.create_simple_embed(
                f"Translated `{result.src}` → `en`",
                result.text
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = self.create_error_embed("Translation Error", str(e))
            await interaction.followup.send(embed=embed)
        
    utils = app_commands.Group(name="utils", description="Utility commands")

    @utils.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, sides)
        embed = self.create_simple_embed("Dice Result:", f"You rolled a {result}")
        await interaction.response.send_message(embed=embed)

    @utils.command(
        name="eye",
        description="3y3 - credits to Twilight Sparkle (@yourcompanionAI)!"
    )
    async def secondsightify_slash(self, interaction: discord.Interaction, text: str):
        result, concealed = secondsightify(text)
        if concealed:
           result = result + "\n\n👆 Copy this!"
        embed = self.create_simple_embed("Eye Result:", result)
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
        embed = self.create_simple_embed("Result:", final)
        await interaction.followup.send(embed=embed)
        
    @utils.command(name="translate", description="Translate text into English")
    async def translate_cmd(
        self,
        interaction: discord.Interaction,
        text: str
    ):
        await interaction.response.defer()

        translator = Translator()
        
        try:
            result = await translator.translate(text, src="auto", dest="en")
            embed = self.create_simple_embed(
                f"Translated `{result.src}` to `en`",
                result.text
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = self.create_error_embed("Translation Error", str(e))
            await interaction.followup.send(embed=embed)
            
    @utils.command(name="ocr", description="Read / extract text from an image.")
    async def readtext(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer()

        # check type early
        if not image.content_type or not image.content_type.startswith("image/"):
            embed = self.create_error_embed("Invalid file", "Please upload a valid image file.")
            await interaction.followup.send(embed=embed)
            return

        try:
            # safe load
            image_bytes = await image.read()
            try:
                img = Image.open(io.BytesIO(image_bytes))
            except UnidentifiedImageError:
                embed = self.create_error_embed(
                    "Unsupported format",
                    f"Sorry, I can’t read this image format (`{image.content_type}`).\n"
                    "Try converting it to PNG or JPG first."
                )
                await interaction.followup.send(embed=embed)
                return

            # OCR
            try:
                text = pytesseract.image_to_string(img)
                if not text.strip():
                    text = "No text found in the image."
                embed = self.create_simple_embed("OCR Result:", text)
            except Exception as e:
                embed = self.create_error_embed("OCR Failed", f"Error while reading text: `{e}`")

        except Exception as e:
            embed = self.create_error_embed("Unexpected error", str(e))

        await interaction.followup.send(embed=embed)


    # context menu
    async def ocr_message(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            embed = self.create_error_embed("No attachments", "Message has no attachments.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        image = message.attachments[0]
        if not image.content_type or not image.content_type.startswith("image/"):
            embed = self.create_error_embed(
                "Not an image",
                "This message doesn’t contain a valid image attachment."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        try:
            image_bytes = await image.read()
            try:
                img = Image.open(io.BytesIO(image_bytes))
            except UnidentifiedImageError:
                embed = self.create_error_embed(
                    "Unsupported format",
                    f"I can’t identify this image format (`{image.content_type}`) !  \n"
                    "Please use PNG or JPG !"
                )
                await interaction.followup.send(embed=embed)
                return

            try:
                text = pytesseract.image_to_string(img)
                if not text.strip():
                    text = "No text found in the image."
                embed = self.create_simple_embed("OCR Result:", text)
            except Exception as e:
                embed = self.create_error_embed("OCR Failed", f"Error while reading text: `{e}`")

        except Exception as e:
            embed = self.create_error_embed("Unexpected error", str(e))

        await interaction.followup.send(embed=embed)

    @utils.command(
        name="lens", 
        description="Reverse image search"
    )
    async def lens(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer()  # Allow more time
        embed = discord.Embed(
            title="Google Lens Results",
            colour=self.accent,
            timestamp=datetime.now()
        )
        embed.set_footer(text=self.emoji)
        image_url = image.url

        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": serp_key
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        visual_matches = results.get("visual_matches", [])
        related_content = results.get("related_content", [])
        if related_content:
            related_links = "\n".join(f"[{r.get('query')}]({r.get('link')})" for r in related_content[:8])
            embed.add_field(name="Related Content", value=related_links + "\n", inline=False)
            
        if not visual_matches:
            embed = self.create_error_embed("Reverse image search failed", "No matches.")
            await interaction.followup.send(embed=embed)
            return
            
        for match in visual_matches[:1]:
            thumbnail = match.get("thumbnail")
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
                
        for match in visual_matches[:8]:
            title = match.get("title", "No title")
            link = match.get("link", "No link")
            embed.add_field(name=title, value=link, inline=False)
                
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))
