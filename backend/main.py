import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import cv2
import subprocess

app = FastAPI()

# --- 1. CORS Configuration (CRITICAL for Local/Cloud mixed access) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Streamlit to communicate with FastAPI
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. Storage Configuration ---
# Use an absolute path relative to the script location
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_ROOT = BASE_DIR / "storage"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# Mount storage
app.mount("/view_storage", StaticFiles(directory=str(STORAGE_ROOT)), name="storage")

def apply_rotation(img, angle: int):
    if angle == 90: return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180: return cv2.rotate(img, cv2.ROTATE_180)
    if angle == 270: return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img

def get_storage_path(subfolder: str):
    today = datetime.now().strftime("%Y-%m-%d")
    path = STORAGE_ROOT / today / subfolder
    path.mkdir(parents=True, exist_ok=True)
    return path

def find_original_file(filename: str):
    matches = list(STORAGE_ROOT.glob(f"**/originals/{filename}"))
    return matches[0] if matches else None

@app.post("/shrink")
async def process_image(file: UploadFile = File(...), width: int = 1280, rotate: int = 0):
    orig_dir = get_storage_path("originals")
    shrunk_dir = get_storage_path("shrunk")
    
    file_path = orig_dir / file.filename
    shrunk_filename = f"{Path(file.filename).stem}.webp"
    shrunk_path = shrunk_dir / shrunk_filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    img = cv2.imread(str(file_path))
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    if rotate in [90, 180, 270]:
        img = apply_rotation(img, rotate)
        cv2.imwrite(str(file_path), img)

    h, w = img.shape[:2]
    aspect = h / w
    target_h = int(width * aspect)
    shrunk_img = cv2.resize(img, (width, target_h), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(shrunk_path), shrunk_img, [cv2.IMWRITE_WEBP_QUALITY, 80])

    # Return relative path
    rel_url = f"view_storage/{datetime.now().strftime('%Y-%m-%d')}/shrunk/{shrunk_filename}"
    return {
        "relative_url": rel_url,
        "width": width, "height": target_h,
        "savings": f"{os.path.getsize(file_path) / os.path.getsize(shrunk_path):.1f}x smaller"
    }

@app.post("/upscale")
async def upscale_image(file_key: str = Query(...)):
    original_path = find_original_file(file_key)
    if not original_path:
        raise HTTPException(status_code=404, detail="File not found")

    orig_img = cv2.imread(str(original_path))
    oh, ow = orig_img.shape[:2]

    # Find Shrunk
    shrunk_filename = f"{Path(file_key).stem}.webp"
    shrunk_matches = list(STORAGE_ROOT.glob(f"**/shrunk/{shrunk_filename}"))
    shrunk_url, s_res = None, "N/A"
    
    if shrunk_matches:
        date_folder = shrunk_matches[0].parent.parent.name
        shrunk_url = f"view_storage/{date_folder}/shrunk/{shrunk_filename}"
        s_img = cv2.imread(str(shrunk_matches[0]))
        if s_img is not None: s_res = f"{s_img.shape[1]}x{s_img.shape[0]}"

    up_dir = get_storage_path("upscaled")
    out_path = up_dir / f"upscaled_{file_key}"
    
    # AI logic
    if os.path.exists("inference_realesrgan.py"):
        subprocess.run(["python", "inference_realesrgan.py", "-n", "RealESRGAN_x4plus", "-i", str(original_path), "-o", str(out_path)], check=True)
        enh = cv2.imread(str(out_path))
        if enh.shape[1] != ow or enh.shape[0] != oh:
            enh = cv2.resize(enh, (ow, oh), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(str(out_path), enh)
    else:
        cv2.imwrite(str(out_path), cv2.resize(orig_img, (ow, oh), interpolation=cv2.INTER_CUBIC))

    return {
        "original_url": f"view_storage/{original_path.parent.parent.name}/originals/{file_key}",
        "shrunk_url": shrunk_url,
        "upscaled_url": f"view_storage/{datetime.now().strftime('%Y-%m-%d')}/upscaled/upscaled_{file_key}",
        "orig_res": f"{ow}x{oh}", "shrunk_res": s_res, "up_res": f"{ow}x{oh}"
    }