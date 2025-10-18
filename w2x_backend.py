"""
FastAPI backend for waifu2x-ncnn-vulkan that accepts an uploaded image and upscales it.
Includes a very basic HTML frontend for uploading files.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
import subprocess
import tempfile
import shutil
import os
import uuid
import pathlib
import logging

app = FastAPI(title="waifu2x-ncnn-vulkan backend")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_waifu2x(in_path: str, out_path: str, scale: int = 2, noise: int = 3, tile: int = 400, gpu: int = 0, extra_args: list | None = None):
    cmd = [
        "waifu2x-ncnn-vulkan",
        "-i", in_path,
        "-o", out_path,
        "-s", str(scale),
        "-n", str(noise),
        "-t", str(tile),
        "-g", str(gpu),
        "-m", "models-upconv_7_photo",
    ]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
    <head><title>Waifu2x Upscaler</title></head>
    <body>
        <h2>Waifu2x Upscaler</h2>
        <form action="/upscale" method="post" enctype="multipart/form-data">
            <label>Select image:</label><br>
            <input type="file" name="file" accept="image/*" required><br><br>

            <label>Passes (default 2):</label>
            <input type="number" name="passes" value="2" min="1" max="4"><br><br>

            <label>Scale (1 or 2):</label>
            <input type="number" name="scale" value="2" min="1" max="2"><br><br>

            <label>Noise (-1 to 3):</label>
            <input type="number" name="noise" value="0" min="-1" max="3"><br><br>

            <label>Tile size:</label>
            <input type="number" name="tile" value="400" min="32"><br><br>

            <label>GPU (index):</label>
            <input type="number" name="gpu" value="0" min="0"><br><br>

            <button type="submit">Upscale</button>
        </form>
    </body>
    </html>
    """

@app.post("/upscale")
async def upscale(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    passes: int = Query(2, ge=1, le=4),
    scale: int = Query(2, ge=1, le=2),
    noise: int = Query(0, ge=-1, le=3),
    tile: int = Query(400, ge=32),
    gpu: int = Query(0, ge=0),
):
    original_filename = pathlib.Path(file.filename).name or f"upload_{uuid.uuid4().hex}.png"
    suffix = pathlib.Path(original_filename).suffix or ".png"

    tmp_dir = tempfile.mkdtemp(prefix="waifu2x_")
    in_path = os.path.join(tmp_dir, "in" + suffix)
    with open(in_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    current_in = in_path
    for pass_idx in range(1, passes + 1):
        current_out = os.path.join(tmp_dir, f"pass_{pass_idx}" + suffix)
        _run_waifu2x(current_in, current_out, scale=scale, noise=noise, tile=tile, gpu=gpu)
        current_in = current_out

    out_path = current_in

    def iterfile(path):
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 64):
                yield chunk

    # Schedule cleanup *after* the response finishes
    background_tasks.add_task(shutil.rmtree, tmp_dir, ignore_errors=True)

    final_name = f"upscaled_{original_filename}"
    media_type = "image/png" if suffix.lower() == ".png" else "application/octet-stream"
    headers = {"Content-Disposition": f"attachment; filename=\"{final_name}\""}

    return StreamingResponse(iterfile(out_path), media_type=media_type, headers=headers)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6969)
