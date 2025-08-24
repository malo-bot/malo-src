import os
import tempfile
import yt_dlp
import secrets
import asyncio
import random
import re
import yaml 

# Load config once
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

branding = config["branding"]

MAX_DISCORD_FILESIZE = 10 * 1024 * 1024  # 10 MB

# Text functions
fullwidth_map = {
    ord(' '): '\u3000',
    ord('.'): '\uFF0E',
}
# Add all ASCII printable chars from '!' to '~'
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

# Media functions
def generate_filename(extension: str) -> str:
    rand = secrets.token_hex(16)
    return f"{branding}_{rand}.{extension}"

def generate_prefix():
    rand = secrets.token_hex(16)
    return f"{branding}_{rand}_"

def download_video_sync(url: str) -> str:
    # calls yt-dlp
    prefix = generate_prefix()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    output_path = os.path.join(tmpdir, "video.%(ext)s")

    ydl_opts = {
        "outtmpl": output_path,
        "format": (
            "best[filesize<=134217728]"
            "/bestvideo[filesize<=134217728]+bestaudio[filesize<=134217728]"
            "/bestvideo+bestaudio/best"
        ),
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "no_warnings": True,
        "source_address": "0.0.0.0"
        # one could add ytsearch if wanted...
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        if not filepath.endswith(".mp4"):
            filepath = filepath.rsplit(".", 1)[0] + ".mp4"

    final_path = os.path.join(tmpdir, generate_filename("mp4"))
    os.replace(filepath, final_path)

    return final_path


async def download_video(url: str) -> str:
    return await asyncio.to_thread(download_video_sync, url)