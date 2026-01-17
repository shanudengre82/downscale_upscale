import subprocess
import time
import sys
import os

def run_dev():
    # Use the same python that is running this script
    python_exe = sys.executable
    
    # Force current directory into path
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    print("🛰️  Starting Backend...")
    # Using 'python -m uvicorn' ensures we use the installed package in the current venv
    backend_proc = subprocess.Popen([
        python_exe, "-m", "uvicorn", "backend.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ], env=env)

    time.sleep(5) # Give the backend more time to load OpenCV

    print("🎨 Starting Frontend...")
    frontend_proc = subprocess.Popen([
        python_exe, "-m", "streamlit", "run", "frontend/app.py",
        "--server.address", "0.0.0.0",
        "--server.port", "8501"
    ], env=env)

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    run_dev()