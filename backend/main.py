import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.staticfiles import StaticFiles
import cv2
import subprocess

app = FastAPI()

# --- 1. Storage Configuration ---
if os.path.exists("/.dockerenv"):
    STORAGE_ROOT = Path("/app/storage")
else:
    STORAGE_ROOT = Path(__file__).parent.parent / "storage"

STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/view_storage", StaticFiles(directory=STORAGE_ROOT), name="storage")

# --- Helper Functions ---

def apply_rotation(img, angle: int):
    """Rotates the image by 90, 180, or 270 degrees clockwise."""
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img

def get_storage_path(subfolder: str):
    today = datetime.now().strftime("%Y-%m-%d")
    path = STORAGE_ROOT / today / subfolder
    path.mkdir(parents=True, exist_ok=True)
    return path

def find_original_file(filename: str):
    matches = list(STORAGE_ROOT.glob(f"**/originals/{filename}"))
    return matches[0] if matches else None

# --- 2. Endpoints ---

@app.post("/shrink")
async def process_image(file: UploadFile = File(...), width: int = 1280, rotate: int = 0):
    orig_dir = get_storage_path("originals")
    shrunk_dir = get_storage_path("shrunk")

    file_path = orig_dir / file.filename
    shrunk_filename = f"{Path(file.filename).stem}.webp"
    shrunk_path = shrunk_dir / shrunk_filename

    # Save Uploaded File
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Load Image
    img = cv2.imread(str(file_path))
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # 1. Apply Rotation if requested
    if rotate in [90, 180, 270]:
        img = apply_rotation(img, rotate)
        # Overwrite the saved original with the rotated version
        # This ensures future Upscaling uses the correct orientation
        cv2.imwrite(str(file_path), img)

    # 2. Process Shrink
    orig_h, orig_w = img.shape[:2]
    aspect_ratio = orig_h / orig_w
    target_height = int(width * aspect_ratio)

    shrunk_img = cv2.resize(img, (width, target_height), interpolation=cv2.INTER_AREA)

    # Write Shrunk WebP
    success = cv2.imwrite(str(shrunk_path), shrunk_img, [cv2.IMWRITE_WEBP_QUALITY, 80])

    if not success:
        raise HTTPException(status_code=500, detail="OpenCV failed to write WebP.")

    relative_url = f"view_storage/{datetime.now().strftime('%Y-%m-%d')}/shrunk/{shrunk_filename}"

    return {
        "message": "File processed",
        "relative_url": relative_url,
        "width": width,
        "height": target_height,
        "savings": f"{os.path.getsize(file_path) / os.path.getsize(shrunk_path):.1f}x smaller",
    }


@app.post("/upscale")
async def upscale_image(file_key: str = Query(...)):
    original_path = find_original_file(file_key)
    if not original_path:
        raise HTTPException(status_code=404, detail="Original file not found")

    # Read the (already rotated) original image
    orig_img = cv2.imread(str(original_path))
    if orig_img is None:
        raise HTTPException(status_code=400, detail="Could not read original image")
    orig_h, orig_w = orig_img.shape[:2]

    # Locate the Shrunk version for comparison
    shrunk_filename = f"{Path(file_key).stem}.webp"
    shrunk_matches = list(STORAGE_ROOT.glob(f"**/shrunk/{shrunk_filename}"))
    shrunk_url = None
    shrunk_res = "N/A"
    
    if shrunk_matches:
        date_folder = shrunk_matches[0].parent.parent.name
        shrunk_url = f"view_storage/{date_folder}/shrunk/{shrunk_filename}"
        s_img = cv2.imread(str(shrunk_matches[0]))
        if s_img is not None:
            shrunk_res = f"{s_img.shape[1]}x{s_img.shape[0]}"

    upscaled_dir = get_storage_path("upscaled")
    upscaled_filename = f"upscaled_{file_key}"
    output_path = upscaled_dir / upscaled_filename
    date_now = datetime.now().strftime("%Y-%m-%d")

    try:
        if os.path.exists("inference_realesrgan.py"):
            subprocess.run(
                [
                    "python", "inference_realesrgan.py",
                    "-n", "RealESRGAN_x4plus",
                    "-i", str(original_path),
                    "-o", str(output_path),
                ],
                check=True,
            )

            enhanced_img = cv2.imread(str(output_path))
            if enhanced_img.shape[1] != orig_w or enhanced_img.shape[0] != orig_h:
                final_img = cv2.resize(
                    enhanced_img, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4
                )
                cv2.imwrite(str(output_path), final_img)
        else:
            # High-quality fallback
            upscaled_img = cv2.resize(orig_img, (orig_w, orig_h), interpolation=cv2.INTER_CUBIC)
            cv2.imwrite(str(output_path), upscaled_img)

        orig_date = original_path.parent.parent.name
        return {
            "message": "Upscale successful",
            "original_url": f"view_storage/{orig_date}/originals/{file_key}",
            "shrunk_url": shrunk_url,
            "upscaled_url": f"view_storage/{date_now}/upscaled/{upscaled_filename}",
            "orig_res": f"{orig_w}x{orig_h}",
            "shrunk_res": shrunk_res,
            "up_res": f"{orig_w}x{orig_h}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upscaling failed: {str(e)}")