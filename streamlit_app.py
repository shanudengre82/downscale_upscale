import streamlit as st
import io
import requests
from PIL import Image, ImageOps
from streamlit_image_comparison import image_comparison
import math
import subprocess
import os
import sys

st.set_page_config(page_title="AI Storage & Upscale", layout="wide")
st.title("🖼️ AI Image Optimizer")

BACKEND_URL = "http://127.0.0.1:8000"
MIN_RES = 200 

def start_backend():
    """Starts the FastAPI backend as a background process."""
    if "backend_started" not in st.session_state:
        # Check if backend is already responding (prevents multiple spawns)
        try:
            response = requests.get("http://127.0.0.1:8000/docs", timeout=1)
            if response.status_code == 200:
                st.session_state.backend_started = True
                return
        except:
            pass

        st.info("🚀 Starting AI Backend...")
        python_exe = sys.executable
        # Use absolute path to the backend main file
        backend_path = os.path.join(os.getcwd(), "backend", "main.py")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()

        subprocess.Popen([
            python_exe, "-m", "uvicorn", "backend.main:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ], env=env)
        
        # Wait for backend to warm up
        time.sleep(5)
        st.session_state.backend_started = True
        st.rerun()

# Call this at the very beginning of your app
start_backend()

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png", "webp"])

if uploaded_file:
    # --- 1. Rotation Control ---
    st.sidebar.subheader("Image Orientation")
    # This allows users to fix upside-down or sideways images before processing
    rotate_angle = st.sidebar.selectbox(
        "Rotate Image (Clockwise)", 
        options=[0, 90, 180, 270],
        format_func=lambda x: f"{x}°"
    )

    # Load image and handle EXIF + Manual Rotation
    orig_pil = Image.open(uploaded_file)
    orig_pil = ImageOps.exif_transpose(orig_pil) # Fixes smartphone auto-rotation
    
    if rotate_angle != 0:
        # PIL rotate uses counter-clockwise, so we negate the angle
        orig_pil = orig_pil.rotate(-rotate_angle, expand=True)
    
    orig_w, orig_h = orig_pil.size

    # Always visible preview
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Original Details")
        st.write(f"📐 **Resolution:** {orig_w} x {orig_h}")
        st.write(f"💾 **File Size:** {uploaded_file.size / 1024:.1f} KB")
        if rotate_angle != 0:
            st.info(f"🔄 Rotated {rotate_angle}° for processing.")
    with col2:
        st.image(orig_pil, caption="Current Preview", use_container_width=True)

    st.divider()

    # Sidebar Controls
    action = st.sidebar.selectbox("Action", ["Shrink for Storage", "AI Upscale"])

    if action == "Shrink for Storage":
        # 95% reduction means the image is 5% of its original width
        # Factor = 1 / 0.05 = 20.0
        MAX_ALLOWED_FACTOR = 20.0 
        
        # Calculate the actual max factor based on your MIN_RES (don't go smaller than 400px)
        # If 95% makes it 200px, this will cap it at 400px instead.
        safe_max_factor = min(MAX_ALLOWED_FACTOR, orig_w / MIN_RES)

        # Create distinct percentage steps: 0% (orig), 25%, 50%, 75%, 90%, 95%
        # Expressed as divisors: 1.0, 1.33, 2.0, 4.0, 10.0, 20.0
        desired_steps = [1.0, 2.0, 4.0, 10.0, round(safe_max_factor, 1)]
        
        # Filter steps that are physically possible given the MIN_RES
        steps = sorted(list(set([s for s in desired_steps if orig_w / s >= MIN_RES])))

        # Mapping steps to user-friendly labels (showing the % reduced)
        option_map = {}
        for s in steps:
            percent_reduction = int((1 - 1 / s) * 100)
            target_w = int(orig_w / s)
            label = f"Reduce by {percent_reduction}% (Target: {target_w}px)"
            option_map[label] = target_w

        selected_label = st.sidebar.selectbox("Select Shrink Level", list(option_map.keys()))
        target_width = option_map[selected_label]

        if st.sidebar.button("Optimize Now"):
            with st.spinner("Processing & Rotating..."):
                # 1. Convert the rotated PIL image back into bytes
                # This ensures the backend gets the image exactly as you see it in the preview
                buf = io.BytesIO()
                # We save it in its original format (or PNG/JPEG)
                img_format = uploaded_file.type.split("/")[-1].upper()
                if img_format == "JPG": img_format = "JPEG"
                
                orig_pil.save(buf, format=img_format)
                rotated_bytes = buf.getvalue()

                # 2. Prepare the files for the request
                files = {
                    "file": (
                        uploaded_file.name,
                        rotated_bytes,
                        uploaded_file.type,
                    )
                }
                
                # 3. Send to backend (we no longer need to pass 'rotate' as a param 
                # because the bytes are already rotated, but we keep it 0 to be safe)
                res = requests.post(
                    f"{BACKEND_URL}/shrink", 
                    params={"width": target_width, "rotate": 0}, 
                    files=files
                )

                if res.status_code == 200:
                    data = res.json()
                    # Add a cache-buster timestamp to the URL so Streamlit doesn't show old versions
                    import time
                    ts = int(time.time())
                    processed_url = f"{BACKEND_URL}/{data['relative_url']}?t={ts}"
                    
                    st.markdown(f"### 📉 Compression Results")
                    c1, c2 = st.columns(2)
                    c1.metric("Original Res", f"{orig_w} x {orig_h}")
                    c2.metric("Shrunk Res", f"{data['width']} x {data['height']}", delta=data['savings'])

                    image_comparison(
                        img1=orig_pil, 
                        img2=processed_url, 
                        label1=f"Original ({orig_w}x{orig_h})", 
                        label2=f"Shrunk ({data['width']}x{data['height']})"
                    )

    elif action == "AI Upscale":
        if st.sidebar.button("Run AI Enhancement"):
            with st.spinner("Processing..."):
                res = requests.post(f"{BACKEND_URL}/upscale", params={"file_key": uploaded_file.name})

                if res.status_code == 200:
                    data = res.json()
                    import time
                    ts = int(time.time())
                    
                    orig_url = f"{BACKEND_URL}/{data['original_url']}?t={ts}"
                    shrunk_url = f"{BACKEND_URL}/{data['shrunk_url']}?t={ts}" if data["shrunk_url"] else None
                    upscale_url = f"{BACKEND_URL}/{data['upscaled_url']}?t={ts}"

                    tab1, tab2, tab3 = st.tabs(["🚀 AI Upscale", "📉 Shrunk", "🖼️ Full Original"])

                    with tab1:
                        image_comparison(
                            img1=orig_url,
                            img2=upscale_url,
                            label1=f"Original ({data['orig_res']})", 
                            label2=f"AI Enhanced ({data['up_res']})",
                            make_responsive=True,
                            starting_position=50
                        )

                    with tab2:
                        if shrunk_url:
                            st.write(f"### Shrunk Image: {data['shrunk_res']}")
                            st.image(shrunk_url, use_container_width=True)
                        else:
                            st.warning("No shrunk version found.")
                    
                    with tab3:
                        if orig_url:
                            st.write(f"### Original Saved Image: {data['orig_res']}")
                            st.image(orig_url, use_container_width=True)
                else:
                    st.error("Make sure to run 'Shrink' first to save and rotate the image on the server.")