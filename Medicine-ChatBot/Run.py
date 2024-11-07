import subprocess

# Start the backend
backend = subprocess.Popen(["python", "gemini-test.py"])

# Start the frontend
frontend = subprocess.Popen(["streamlit", "run", "ui.py"])

# Optionally, monitor both processes
try:
    while backend.poll() is None and frontend.poll() is None:
        pass
except KeyboardInterrupt:
    # Clean up if the script is interrupted
    backend.terminate()
    frontend.terminate()
