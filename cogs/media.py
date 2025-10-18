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
from helper import download_video, generate_filename, upscale
import subprocess
from pathlib import Path
from .KatyaCog import KatyaCog  # import base cog
# yes im lazy.
MAX_DISCORD_FILESIZE = 10 * 1024 * 1024  # 10 MB
MAX_GIF_SIZE = MAX_DISCORD_FILESIZE

class Media(KatyaCog):  # inherit from KatyaCog
    def __init__(self, bot):
        super().__init__(bot)
        
        self.togif_ctx = app_commands.ContextMenu(
            name="To GIF",
            callback=self.togif_cmd,
        )
        
        self.togif_ctx.allowed_installs = app_commands.AppInstallationType(guild=True, user=True)
        self.togif_ctx.allowed_contexts = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
        
        bot.tree.add_command(self.togif_ctx)
        
    media = app_commands.Group(
        name="media",
        description="Media commands"
    )
    
    async def togif_cmd(self, interaction: discord.Interaction, message: discord.Message):

        if not message.attachments:
            embed = self.create_error_embed("No attachments", "No attachments found in message.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        media = message.attachments[0]
        if not media.content_type or not (
            media.content_type.startswith("video/") or media.content_type.startswith("image/")
        ):
            embed = self.create_error_embed("Invalid File", "Please upload a valid **video** or **image** file.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)
            
        await interaction.response.defer()
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, generate_filename(media.filename.split('.')[-1]))
            palette_path = os.path.join(tmpdir, generate_filename("png"))
            output_path = os.path.join(tmpdir, generate_filename("gif"))

            await media.save(input_path)

            scale = 480
            fps = 15
            duration_trim = 120

            palette_cmd = [
                "ffmpeg", "-y", "-hide_banner",
                "-i", input_path,
                "-t", str(duration_trim),
                "-vf", f"fps={fps},scale={scale}:-1:flags=bicubic,palettegen",
                palette_path
            ]

            try:
                subprocess.run(palette_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to generate palette:\n```{e.stderr.decode()}```")
                return await interaction.followup.send(embed=embed)

            def run_gif(scale):
                gif_cmd = [
                    "ffmpeg", "-y", "-hide_banner",
                    "-i", input_path,
                    "-i", palette_path,
                    "-t", str(duration_trim),
                    "-lavfi", f"fps={fps},scale={scale}:-1:flags=bicubic [x]; [x][1:v] paletteuse=dither=none",
                    output_path
                ]
                subprocess.run(gif_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            try:
                run_gif(scale)
                while os.path.getsize(output_path) > MAX_GIF_SIZE and scale > 64:
                    scale = max(int(scale * 0.8), 64)
                    run_gif(scale)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to convert media:\n```{e.stderr.decode()}```")
                return await interaction.followup.send(embed=embed)

            await interaction.followup.send(file=discord.File(output_path, filename=os.path.basename(output_path)))
    
    @media.command(name="download", description="Download media from an URL")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def download(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(thinking=True)

        try:
            filepath = await download_video(url)
        except Exception as e:
            embed = self.create_error_embed("Download Failed", f"Failed to download: {e}")
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
                                embed = self.create_error_embed("Upload failed", f"Uguu API returned status: {resp}")
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
                "ffmpeg", "-y", "-hide_banner",
                "-i", input_path,
                "-t", str(duration_trim),
                "-vf", f"fps={fps},scale={scale}:-1:flags=bicubic,palettegen",
                palette_path
            ]

            try:
                subprocess.run(palette_cmd, check=True)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to generate palette: {e}")
                return await interaction.followup.send(embed=embed)

            gif_cmd = [
                "ffmpeg", "-y", "-hide_banner",
                "-i", input_path,
                "-i", palette_path,
                "-t", str(duration_trim),
                "-lavfi", f"fps={fps},scale={scale}:-1:flags=bicubic [x]; [x][1:v] paletteuse=dither=none",
                output_path
            ]

            try:
                subprocess.run(gif_cmd, check=True)
            except subprocess.CalledProcessError as e:
                embed = self.create_error_embed("GIF Conversion Failed", f"Failed to convert media to GIF: {e}")
                return await interaction.followup.send(embed=embed)

            # loop shrink
            while os.path.getsize(output_path) > MAX_GIF_SIZE and scale > 64:
                scale = max(int(scale * 0.8), 64)
                gif_cmd[7] = f"fps={fps},scale={scale}:-1:flags=bicubic [x]; [x][1:v] paletteuse=dither=none"
                subprocess.run(gif_cmd, check=True)

            await interaction.followup.send(file=discord.File(output_path, filename=os.path.basename(output_path)))
            
    @media.command(
        name="upscale",
        description="Upscale an image 2x"
    )
    @app_commands.describe(
        image="The image to upscale",
        noise="0 to 3"
    )
    async def upscale_command(self, interaction: discord.Interaction, image: discord.Attachment, noise: int = 3):
        await interaction.response.defer()  # Show "thinking" status
        try:
            # Clamp noise value
            noise = max(0, min(3, noise))
            # Run your upscale function
            output_path = await upscale(image, noise=noise)

            # Send the resulting file
            await interaction.followup.send(file=discord.File(output_path))

            # Clean up temp file
            if os.path.exists(output_path):
                os.remove(output_path)

        except Exception as e:
            embed = self.create_error_embed("Upscaling error", e)
            return await interaction.followup.send(embed=embed)

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
                embed = self.create_error_embed("FFmpeg error", f"\n{stderr.decode()[:1900]}\n")
                return await interaction.followup.send(embed=embed)

            # send compressed file back
            await interaction.followup.send(file=discord.File(output_path, filename=os.path.basename(output_path)))

        finally:
            # cleanup
            for path in [input_path, output_path]:
                try: os.remove(path)
                except: pass
                
    @media.command(name="split", description="Split a mp4 into video and audio (mp3)")
    async def split_streams(self, interaction: discord.Interaction, video: discord.Attachment):
        await interaction.response.defer()  # allows processing time for large files
        
        if not video.content_type or not video.content_type.startswith("video/"):
            embed = self.create_error_embed("Invalid File", "Please upload a valid video file.")
            return await interaction.followup.send(embed=embed)
            
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            input_file = tmpdir_path / generate_filename("mp4")
            video_file = tmpdir_path / generate_filename("mp4")
            audio_file = tmpdir_path / generate_filename("mp3")

            # Download the video
            await video.save(input_file)

            # Video-only command (copy video, drop audio)
            cmd_video = [
                "ffmpeg", "-y", "-hide_banner",
                "-i", str(input_file),
                "-c:v", "copy",
                "-an",  # drop audio
                str(video_file)
            ]

            # Audio-only command (drop video, encode audio as MP3)
            cmd_audio = [
                "ffmpeg", "-y", "-hide_banner",
                "-i", str(input_file),
                "-vn",  # drop video
                "-c:a", "libmp3lame",
                "-q:a", "2",  # good quality VBR
                str(audio_file)
            ]

            # Run both commands asynchronously
            process_video = await asyncio.create_subprocess_exec(
                *cmd_video,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            process_audio = await asyncio.create_subprocess_exec(
                *cmd_audio,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout_v, stderr_v = await process_video.communicate()
            stdout_a, stderr_a = await process_audio.communicate()

            # Check for errors
            if process_video.returncode != 0:
                embed = self.create_error_embed("FFmpeg Error", stderr_v.decode())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if process_audio.returncode != 0:
                embed = self.create_error_embed("FFmpeg Error", stderr_a.decode())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Send files back
            files = [
                discord.File(video_file, filename=video_file.name),
                discord.File(audio_file, filename=audio_file.name)
            ]
            await interaction.followup.send(files=files)

    @media.command(name="trim", description="Trim a video")
    @app_commands.describe(video="Video file to trim", start="Start time in seconds", end="End time in seconds")
    async def trim(self, interaction: discord.Interaction, video: discord.Attachment, start: float, end: float):
        await interaction.response.defer()
        
        if not video.content_type or not video.content_type.startswith("video/"):
            embed = self.create_error_embed("Invalid File", "Please upload a valid video file.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                ext = video.filename.split(".")[-1]
                input_file = os.path.join(temp_dir, f"input_{generate_filename(ext)}")
                output_file = os.path.join(temp_dir, f"output_{generate_filename(ext)}")
                
                await video.save(input_file)
                
                ffmpeg_cmd = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-i", input_file,
                    "-ss", str(start),
                    "-to", str(end),
                    "-c:v", "libx264",  # Re-encode video
                    "-c:a", "aac",      # Re-encode audio
                    "-preset", "ultrafast",  # Balance between speed and file size
                    "-crf", "26",       # Quality setting (0-51, lower is better)
                    output_file
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    embed = self.create_error_embed("FFmpeg Error", stderr.decode())
                    return await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Check if output file exists and has content
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    file = discord.File(output_file)
                    await interaction.followup.send(file=file)
                else:
                    embed = self.create_error_embed("Processing Error", "Output file was not created or is empty")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    
            except Exception as e:
                embed = self.create_error_embed("Error", str(e))
                await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Media(bot))
