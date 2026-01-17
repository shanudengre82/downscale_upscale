import streamlit as st
import requests
import os
import sys
import subprocess
import time
import io
from PIL import Image, ImageOps
from streamlit_image_comparison import image_comparison

# --- 1. Environment Detection & Backend Starter ---
BACKEND_URL = "http://127.0.0.1:8000"


def start_backend_sidecar():
    try:
        # Check if backend is already alive
        requests.get(f"{BACKEND_URL}/view_storage", timeout=1)
    except:
        # Start backend as a sidecar process
        st.info("Initializing AI Engine...")
        py_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()

        # Start FastAPI in background
        subprocess.Popen(
            [
                py_exe,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            env=env,
        )
        time.sleep(5)  # Warm up


start_backend_sidecar()

# --- 2. Main App Interface ---
st.set_page_config(page_title="AI Storage & Upscale", layout="wide")
st.title("🖼️ AI Image Optimizer")

uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png", "webp"])

if uploaded_file:
    # Orientation Logic
    st.sidebar.subheader("Image Orientation")
    rotate_angle = st.sidebar.selectbox(
        "Rotate Image", options=[0, 90, 180, 270], format_func=lambda x: f"{x}°"
    )

    orig_pil = Image.open(uploaded_file)
    orig_pil = ImageOps.exif_transpose(orig_pil)
    if rotate_angle != 0:
        orig_pil = orig_pil.rotate(-rotate_angle, expand=True)

    ow, oh = orig_pil.size

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Details")
        st.write(f"📐 {ow} x {oh}")
    with col2:
        st.image(orig_pil, caption="Original Preview", use_container_width=True)

    st.divider()
    action = st.sidebar.selectbox("Action", ["Shrink for Storage", "AI Upscale"])

    if action == "Shrink for Storage":
        target_width = st.sidebar.slider("Target Width", 200, ow, ow // 2)

        if st.sidebar.button("Process"):
            with st.spinner("Processing..."):
                # Convert rotated PIL to bytes to send to backend
                buf = io.BytesIO()
                orig_pil.save(buf, format="PNG")

                files = {"file": (uploaded_file.name, buf.getvalue(), "image/png")}
                res = requests.post(
                    f"{BACKEND_URL}/shrink", params={"width": target_width}, files=files
                )

                if res.status_code == 200:
                    data = res.json()
                    ts = int(time.time())
                    proc_url = f"{BACKEND_URL}/{data['relative_url']}?t={ts}"

                    st.metric("Savings", data["savings"])
                    image_comparison(
                        img1=orig_pil,
                        img2=proc_url,
                        label1="Original",
                        label2="Shrunk",
                        make_responsive=True,
                    )

    elif action == "AI Upscale":
        if st.sidebar.button("Run AI Upscale"):
            with st.spinner("AI Enhancing..."):
                res = requests.post(
                    f"{BACKEND_URL}/upscale", params={"file_key": uploaded_file.name}
                )
                if res.status_code == 200:
                    data = res.json()
                    ts = int(time.time())

                    o_url = f"{BACKEND_URL}/{data['original_url']}?t={ts}"
                    u_url = f"{BACKEND_URL}/{data['upscaled_url']}?t={ts}"
                    s_url = (
                        f"{BACKEND_URL}/{data['shrunk_url']}?t={ts}"
                        if data["shrunk_url"]
                        else None
                    )

                    t1, t2, t3 = st.tabs(
                        ["🚀 AI Comparison", "📉 Shrunk View", "🖼️ Full Original"]
                    )
                    with t1:
                        image_comparison(
                            img1=o_url,
                            img2=u_url,
                            label1=f"Original ({data['orig_res']})",
                            label2=f"AI Enhanced",
                            make_responsive=True,
                        )
                    with t2:
                        if s_url:
                            st.image(
                                s_url,
                                caption=f"Shrunk ({data['shrunk_res']})",
                                use_container_width=True,
                            )
                    with t3:
                        st.image(
                            o_url, caption="Stored Original", use_container_width=True
                        )
