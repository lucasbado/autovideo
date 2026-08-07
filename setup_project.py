import subprocess
import sys
import os

def run_command(command):
    print(f"🚀 Running: {command}")
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing {command}: {e}")
        return False
    return True

def setup():
    print("🛠️ Starting AutoVideo Project Setup...")
    
    # 1. Install Requirements
    if not run_command(f"{sys.executable} -m pip install -r requirements.txt"):
        return

    # 2. Install Playwright Browsers
    print("🌐 Installing Playwright browsers...")
    run_command("playwright install")

    # 3. Download Spacy Model
    print("🧠 Downloading Spacy English model...")
    run_command(f"{sys.executable} -m spacy download en_core_web_sm")

    # 4. Create necessary folders
    directories = ["temp", "outputs", "data", "data/sessions", "vault/agenda", "vault/production"]
    for d in directories:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"📁 Created directory: {d}")

    print("\n✅ Setup complete! You can now run the app using:")
    print("python src/app_gui.py")

if __name__ == "__main__":
    setup()
