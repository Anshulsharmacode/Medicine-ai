import subprocess

# Start the backend
backend = subprocess.Popen(["python", "gemini-test.py"])

# Start the frontend
frontend = subprocess.Popen(["streamlit", "run", "ui.py"])

# Wait for both to complete (this will keep the script running)
backend.wait()
frontend.wait()
