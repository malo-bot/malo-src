import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
import random
import yt_dlp
import aiohttp
import aiofiles
import os
import tempfile
import asyncio
from helper import download_video, generate_filename
import subprocess
from .KatyaCog import KatyaCog  # import base cog

MAX_DISCORD_FILESIZE = 10 * 1024 * 1024  # 10 MB
MAX_GIF_SIZE = MAX_DISCORD_FILESIZE

class Media(KatyaCog):  # inherit from KatyaCog
    def __init__(self, bot):
        super().__init__(bot)
        
    media = app_commands.Group(name="media", description="Media commands")
    
    @media.command(name="download", description="Download from URL")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def download(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(thinking=True)

        try:
            filepath = await download_video(url)
        except Exception as e:
            embed = self.create_error_embed("Download Failed", f"Failed to download: ```{e}```")
            return await interaction.followup.send(embed=embed)

        try:
            filesize = os.path.getsize(filepath)
            if filesize <= MAX_DISCORD_FILESIZE:
                await interaction.followup.send(file=discord.File(filepath, filename=os.path.basename(filepath)))
            else:
                async with aiohttp.ClientSession() as session:
                    async with aiofiles.open(filepath, "rb") as f:
                        form = aiohttp.FormData()
                        form.add_field("files[]", await f.read(), filename=os.path.basename(filepath))
                        async with session.post("https://uguu.se/upload", data=form) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                files = result.get("files")
                                if result.get("success") and files and "url" in files[0]:
                                    future_time = datetime.now(timezone.utc) + timedelta(hours=3)
                                    unix_ts = int(future_time.timestamp())
                                    file_url = result["files"][0]["url"]
                                    await interaction.followup.send(
                                        f"{file_url}\nExpires: <t:{unix_ts}:R>"
                                    )
                                else:
                                    embed = self.create_error_embed("Upload failed", "Uguu API returned invalid response.")
                                    return await interaction.followup.send(embed=embed)
                            else:
                                embed = self.create_error_embed("Upload failed", f"Uguu API returned status: ```{resp}```")
                                return await interaction.followup.send(embed=embed)
        finally:
            # cleanup files
            try:
                os.remove(filepath)
                os.rmdir(os.path.dirname(filepath))
            except Exception:
                pass
    
    @media.command(name="gif", description="Convert an uploaded image or video to a GIF.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def togif(self, interaction: discord.Interaction, media: discord.Attachment):
        await interaction.response.defer()

        if not media.content_type or not (
            media.content_type.startswith("video/") or media.content_type.startswith("image/")
        ):
            embed = self.create_error_embed("Invalid File", "Please upload a valid **video** or **image** file.")
            return await interaction.followup.send(embed=embed)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, generate_filename(media.filename.split('.')[-1]))
            palette_path = os.path.join(tmpdir, generate_filename("png"))
            output_path = os.path.join(tmpdir, generate_filename("gif"))

            await media.save(input_path)

            scale = 480
            fps = 15
            duration_trim = 10  

            palette_cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-t", str(duration_trim),
                "-vf", f"fps={fps},scale={scale}:-1:flags=bicubic,palettegen",
                palette_path
            ]

            try:
                subprocess.run(palette_cmd, check=True)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to generate palette: ```{e}```")
                return await interaction.followup.send(embed=embed)

            gif_cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", palette_path,
                "-t", str(duration_trim),
                "-lavfi", f"fps={fps},scale={scale}:-1:flags=bicubic [x]; [x][1:v] paletteuse=dither=none",
                output_path
            ]

            try:
                subprocess.run(gif_cmd, check=True)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to convert media to GIF: ```{e}```")
                return await interaction.followup.send(embed=embed)

            # loop shrink
            while os.path.getsize(output_path) > MAX_GIF_SIZE and scale > 64:
                scale = max(int(scale * 0.8), 64)
                gif_cmd[7] = f"fps={fps},scale={scale}:-1:flags=bicubic [x]; [x][1:v] paletteuse=dither=none"
                subprocess.run(gif_cmd, check=True)

            await interaction.followup.send(file=discord.File(output_path, filename=os.path.basename(output_path)))

    @media.command(name="worsen", description="Worsen a video's quality")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def compress(self, interaction: discord.Interaction, video: discord.Attachment):
        await interaction.response.defer(thinking=True)

        # ensure it's a video
        if not video.content_type or not video.content_type.startswith("video/"):
            embed = self.create_error_embed("Invalid File", "Please upload a valid video file.")
            return await interaction.followup.send(embed=embed)
            
        temp_dir = tempfile.gettempdir()
        input_path = os.path.join(temp_dir, generate_filename("mp4"))
        output_path = os.path.join(temp_dir, generate_filename("mp4"))

        # download the video
        await video.save(input_path)

         # ffmpeg command
        cmd = [
            "ffmpeg", "-y", "-hide_banner",
            "-i", input_path,
            "-vf", "scale=trunc(iw/2/2)*2:trunc(ih/2/2)*2,fps=15",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "42",  # the answer to life, the universe and everything
            "-c:a", "aac",
            "-b:a", "16k",
            "-af", "volume=5",        # boost audio volume
            output_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                embed = self.create_error_embed("FFmpeg error", f"```\n{stderr.decode()[:1900]}\n```")
                return await interaction.followup.send(embed=embed)

            # send compressed file back
            await interaction.followup.send(file=discord.File(output_path, filename=os.path.basename(output_path)))

        finally:
            # cleanup
            for path in [input_path, output_path]:
                try: os.remove(path)
                except: pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Media(bot))
