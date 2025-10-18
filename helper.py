import os
import tempfile
import yt_dlp
import secrets
import random
import re
import yaml 
import discord
from serpapi import GoogleSearch
import aiohttp
from PIL import Image
import io
import asyncio
import zipfile
import aiofiles
import functools
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB per chunk
async def run_subprocess_async(cmd: list[str]) -> None:
    """Runs a subprocess asynchronously and raises an exception on failure."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"Subprocess failed (code {process.returncode}): {stderr.decode().strip()}")

# Load config once
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
serp_key = config["serp_key"]
branding = config["branding"]

MAX_DISCORD_FILESIZE = 10 * 1024 * 1024  # 10 MB
USE_API = config.get("use_w2x_api_server", False)
WAIFU2X_API_URL = config.get("w2x_baseurl", "http://127.0.0.1:6969/upscale")
GB = 1024 * 1024 * 1024
# TEXT FUNCTIONS 



fullwidth_map = {
    ord(' '): '\u3000',
    ord('.'): '\uFF0E',
}
for c in range(ord('!'), ord('~') + 1):
    fullwidth_map[c] = chr(c + 0xFEE0)

def tofullwidth(s):
    return s.translate(fullwidth_map)

def italicize(text):
    original_lower = 'qwertyuiopasdfghjklzxcvbnm'
    original_upper = 'QWERTYUIOPASDFGHJKLZXCVBNM'
    original_numbers = '0123456789'
    original = original_lower + original_upper + original_numbers  
    replacement = ''.join([
        chr(0x1D622 + (ord(c) - ord('a'))) if c.islower() 
        else chr(0x1D608 + (ord(c) - ord('A'))) if c.isupper() 
        else chr(0x1D7F6 + (ord(c) - ord('0'))) 
        for c in original
    ])
    translation_table = str.maketrans(original, replacement)
    return text.translate(translation_table)
    
original_lower = 'abcdefghijklmnopqrstuvwxyz'
original_upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
original_numbers = '0123456789'
original = original_lower + original_upper + original_numbers

italic_replacement = ''.join([
    chr(0x1D622 + (ord(c) - ord('a'))) if c.islower() else
    chr(0x1D608 + (ord(c) - ord('A'))) if c.isupper() else
    chr(0x1D7E2 + (ord(c) - ord('0')))
    for c in original
])

bold_italic_replacement = ''.join([
    chr(0x1D656 + (ord(c) - ord('a'))) if c.islower() else
    chr(0x1D63C + (ord(c) - ord('A'))) if c.isupper() else
    chr(0x1D7CE + (ord(c) - ord('0')))
    for c in original
])

ITALIC_TRANS = str.maketrans(original, italic_replacement)
BOLD_ITALIC_TRANS = str.maketrans(original, bold_italic_replacement)

def italicize_random(text: str, italic_prob=1.0, bold_prob=0.5) -> str:
    parts = re.split(r'(\W+)', text)
    
    result_parts = []
    for part in parts:
        if not part:  
            continue
        if re.match(r'^\W+$', part):  
            result_parts.append(part)
        else: 
            rand = random.random()
            if rand < bold_prob:
                styled = part.translate(BOLD_ITALIC_TRANS)
            elif rand < bold_prob + italic_prob:
                styled = part.translate(ITALIC_TRANS)
            else:
                styled = part
            result_parts.append(styled)
    
    return ''.join(result_parts)

def secondsightify(t: str) -> tuple[str, bool]:
    if t.startswith("👁") and t.endswith("👁"):
        t = t[1:-1]

    if any(0xE0000 < ord(c) < 0xE007F for c in t):
        revealed = ''.join(
            chr(ord(c) - 0xE0000) if 0xE0000 < ord(c) < 0xE007F else c
            for c in t
        )
        return revealed, False
    else:
        concealed = ''.join(
            chr(ord(c) + 0xE0000) if 0x00 < ord(c) < 0x7F else c
            for c in t
        )
        return f"👁{concealed}👁", True



# MEDIA FUNCTIONS



def generate_filename(extension: str) -> str:
    rand = secrets.token_hex(4)
    return f"{branding}_{rand}.{extension}"

def generate_prefix():
    rand = secrets.token_hex(4)
    return f"{branding}_{rand}_"

def download_video_sync(url: str) -> str:
    import os, tempfile, yt_dlp
    from yt_dlp.utils import DownloadError

    prefix = generate_prefix()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    output_path = os.path.join(tmpdir, "video.%(ext)s")

    is_tiktok = "tiktok.com" in url.lower()

    base_opts = {
        "outtmpl": output_path,
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "source_address": "0.0.0.0",
    }

    # Prefer high quality first
    if is_tiktok:
        format_string = (
            f"best[ext=mp4][filesize<={MAX_DISCORD_FILESIZE}]"
            f"/bestvideo[ext=mp4][filesize<={MAX_DISCORD_FILESIZE}]+bestaudio[ext=m4a]"
            f"/best[ext=mp4]/best"
        )
    else:
        format_string = f"bestvideo[filesize<={GB}]+bestaudio/best"

    ydl_opts = {**base_opts, "format": format_string}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as e:
        # Fallback to safest format if first try fails
        if "Requested format is not available" in str(e):
            print("⚠️ Falling back to 'best' format.")
            ydl_opts["format"] = "best"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        else:
            raise

    filepath = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
    if not filepath.endswith(".mp4"):
        filepath = filepath.rsplit(".", 1)[0] + ".mp4"

    final_path = os.path.join(tmpdir, generate_filename("mp4"))
    os.replace(filepath, final_path)
    return final_path


async def download_video(url: str) -> str:
    return await asyncio.to_thread(download_video_sync, url)
    
async def upscale(file: "discord.Attachment", noise: int = 3) -> str:
    # --- Validate extension ---
    if not any(file.filename.lower().endswith(ext) for ext in ["png", "jpg", "jpeg", "webp"]):
        raise ValueError("Unsupported file type. Please upload PNG, JPG, or WEBP.")

    # --- Clamp noise ---
    MIN_NOISE = -1
    MAX_NOISE = 3
    noise = max(MIN_NOISE, min(MAX_NOISE, noise))
    MAX_DIMENSION = 2000  # px
    extension = file.filename.split(".")[-1].lower()
    output_filename = generate_filename(extension)
    persistent_path = os.path.join(tempfile.gettempdir(), output_filename)

    # --- Check image dimensions before any processing ---
    img_bytes = await file.read()
    try:
        im = Image.open(io.BytesIO(img_bytes))
        if im.width > MAX_DIMENSION or im.height > MAX_DIMENSION:
            raise ValueError(f"Image too large ({im.width}x{im.height}). Max allowed is {MAX_DIMENSION}x{MAX_DIMENSION}px.")
    except Exception as e:
        print(e)
        raise ValueError(e)

    # --- Attempt API if enabled ---
    if USE_API:
        try:
            async with aiohttp.ClientSession() as session:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
                    tmp_file.write(img_bytes)
                    tmp_file.flush()

                    form = aiohttp.FormData()
                    form.add_field("file", open(tmp_file.name, "rb"), filename=file.filename)
                    form.add_field("passes", "1")  # 2x upscale
                    form.add_field("scale", "2")
                    form.add_field("noise", str(noise))

                async with session.post(WAIFU2X_API_URL, data=form, timeout=300) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"Waifu2x API failed ({resp.status}): {text[:400]}")
                    result_bytes = await resp.read()
                    with open(persistent_path, "wb") as f_out:
                        f_out.write(result_bytes)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # If API fails, fall back to local processing
            print(f"API unavailable, falling back to local waifu2x: {e}")
            USE_API_FALLBACK = True
        finally:
            os.remove(tmp_file.name)
    else:
        USE_API_FALLBACK = True

    # --- Local subprocess fallback ---
    if not USE_API or 'USE_API_FALLBACK' in locals():
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, file.filename)
            output_path = os.path.join(tmpdir, output_filename)

            # Save original image to temp
            with open(input_path, "wb") as f:
                f.write(img_bytes)

            # Run waifu2x subprocess
            cmd = [
                "waifu2x-ncnn-vulkan",
                "-i", input_path,
                "-o", output_path,
                "-s", "2",        # 2x upscale
                "-n", str(noise),
                "-m", "/malo/malo-src/extdeps/models-cunet",
                "-g", "-1"
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"Waifu2x failed: {stderr.decode().strip()}")

            # Copy to persistent temp file
            os.replace(output_path, persistent_path)

    return persistent_path


async def perform_lens_search(self, image_url: str):
    start_time = time.perf_counter()

    embed = discord.Embed(
        title="Google Lens Results",
        colour=self.accent,
        timestamp=datetime.now()
    )
    embed.set_footer(text=self.emoji)

    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": serp_key,
        "type": "all",
        "safe": "off"
    }

    try:
        results = await asyncio.to_thread(lambda: GoogleSearch(params).get_dict())
    except Exception as e:
        return self.create_error_embed(
            "Reverse image search failed",
            f"Unexpected error: `{type(e).__name__}: {e}`"
        )

    if "error" in results:
        error_msg = results.get("error", "Unknown API error.")
        if "quota" in error_msg.lower() or "limit" in error_msg.lower():
            friendly_msg = "You’ve hit the SerpAPI quota. Please try again later."
        elif "invalid api key" in error_msg.lower():
            friendly_msg = "The API key is invalid."
        else:
            friendly_msg = error_msg

        return self.create_error_embed(
            "Reverse image search failed",
            friendly_msg
        )

    visual_matches = results.get("visual_matches", [])
    related_content = results.get("related_content", [])

    if related_content:
        related_links = "\n".join(
            f"[{r.get('query','No query')}]({r.get('link','')})"
            for r in related_content[:8]
        )
        embed.add_field(
            name="Related Content",
            value=related_links or "No related links",
            inline=False
        )

    if not visual_matches:
        return self.create_error_embed(
            "Reverse image search failed",
            "No visual matches found."
        )

    first_thumb = visual_matches[0].get("thumbnail")
    if first_thumb:
        embed.set_thumbnail(url=first_thumb)

    for match in visual_matches[:8]:
        title = match.get("title", "No title")
        link = match.get("link", "No link")
        embed.add_field(name=title, value=link, inline=False)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    embed.set_footer(text=f"{self.emoji} • Took {elapsed_ms}ms")
    return embed
