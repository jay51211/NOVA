import os
import time
import platform
import subprocess
import shlex
import sqlite3
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import google.generativeai as genai
from gtts import gTTS
import tempfile

# ========================
# CONFIG
# ========================
load_dotenv()
PORT = int(os.getenv("PORT", 5000))
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-1.5-flash"
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
DB_PATH = Path(__file__).resolve().parent / "users.db"

# ========================
# INITIALIZE APP
# ========================
app = Flask(__name__, static_folder=FRONTEND_DIR, template_folder=FRONTEND_DIR)
CORS(app)

# ========================
# INIT GEMINI MODEL
# ========================
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# ========================
# THREAD-SAFE TTS (SERVER SIDE, optional)
# ========================
def speak_text_async(text: str):
    """Generate TTS in a background thread."""
    def _speak():
        try:
            tmp_path = os.path.join(tempfile.gettempdir(), f"nova_{int(time.time()*1000)}.mp3")
            tts = gTTS(text=text, lang='en')
            tts.save(tmp_path)
            # Optional: play on server (uncomment if needed)
            # from playsound import playsound
            # playsound(tmp_path)
        except Exception as e:
            print("TTS error:", e)
    threading.Thread(target=_speak, daemon=True).start()

# ========================
# DATABASE INIT
# ========================
def _conn():
    return sqlite3.connect(DB_PATH)

def _ensure_table():
    conn = _conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT
    )""")
    conn.commit()
    conn.close()

_ensure_table()

# ========================
# AUTH HELPERS
# ========================
def create_user(username: str, password: str):
    if not username or not password:
        return False, "username and password required"
    conn = _conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  (username, generate_password_hash(password)))
        conn.commit()
        return True, "user created"
    except Exception as e:
        return False, f"error creating user: {e}"
    finally:
        conn.close()

def verify_user(username: str, password: str):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, "user not found"
    return (True, "login successful") if check_password_hash(row[0], password) else (False, "invalid credentials")

# ========================
# APP CONTROL HELPERS
# ========================
APP_MAP = {
    "chrome": {
        "Windows": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "Darwin": "/Applications/Google Chrome.app",
        "Linux": "google-chrome"
    },
    "vscode": {
        "Windows": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "Darwin": "/Applications/Visual Studio Code.app",
        "Linux": "code"
    }
}

def _expand(path):
    return os.path.expandvars(os.path.expanduser(path))

def open_app_by_name(name: str):
    os_name = platform.system()
    key = (name or "").strip().lower()
    if key in APP_MAP:
        path = APP_MAP[key].get(os_name)
        if not path:
            return False, f"No configured path for {name} on {os_name}"
        path = _expand(path)
        try:
            if os_name == "Windows":
                os.startfile(path)
            elif os_name == "Darwin":
                subprocess.Popen(["open", "-a", path])
            else:
                subprocess.Popen(shlex.split(path))
            return True, f"Opened {name}"
        except Exception as e:
            return False, f"Failed to open {name}: {e}"
    try:
        subprocess.Popen(shlex.split(name))
        return True, f"Launched {name} via shell"
    except Exception as e:
        return False, f"Unknown app and shell launch failed: {e}"

def close_app_by_name(name: str):
    os_name = platform.system()
    try:
        if os_name == "Windows":
            subprocess.run(["taskkill", "/f", "/im", f"{name}.exe"], check=False)
        else:
            subprocess.run(["pkill", "-f", name], check=False)
        return True, f"Attempted to close {name}"
    except Exception as e:
        return False, f"Failed to close {name}: {e}"

tmp_path = os.path.join(tempfile.gettempdir(), f"nova_{int(time.time()*1000)}.mp3")


# ========================
# AI HANDLER
# ========================
def ask_nova(prompt: str) -> str:
    try:
        system_prompt = (
            "You are Nova, a friendly AI assistant. "
            "If the user asks a casual question (like 'hi' or 'hello'), respond briefly and conversationally. "
            "If the user asks for help, code, or explanations, give a clear, well-structured answer."
        )
        response = model.generate_content(f"{system_prompt}\nUser: {prompt}\nNova:")
        return response.text.strip()
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

# ========================
# ROUTES
# ========================
@app.route('/')
def index():
    return app.send_static_file("index.html")

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    prompt = (data.get('prompt') or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "empty prompt"}), 400

    lower = prompt.lower()
    if lower.startswith("open ") or lower.startswith("launch "):
        target = prompt.split(' ', 1)[1].strip()
        ok, msg = open_app_by_name(target)
        speak_text_async(msg)
        return jsonify({"ok": ok, "text": msg}), (200 if ok else 500)
    if lower.startswith("close ") or lower.startswith("terminate "):
        target = prompt.split(' ', 1)[1].strip()
        ok, msg = close_app_by_name(target)
        speak_text_async(msg)
        return jsonify({"ok": ok, "text": msg}), (200 if ok else 500)

    reply = ask_nova(prompt)
    speak_text_async(reply)
    return jsonify({"ok": True, "text": reply})

@app.route("/api/say_browser", methods=["POST"])
def say_browser():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400
    try:
        tts = gTTS(text=text, lang="en")
        # Use a temp file path, not an open file
        tmp_path = os.path.join(tempfile.gettempdir(), f"nova_{int(time.time()*1000)}.mp3")
        tts.save(tmp_path)  # Save directly to path

        # Send file and delete after response
        def remove_file(response):
            try:
                os.remove(tmp_path)
            except Exception as e:
                print("Failed to delete temp file:", e)
            return response

        response = send_file(tmp_path, mimetype="audio/mpeg")
        response.call_on_close(lambda: remove_file(response))
        return response
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json() or {}
    u = (data.get('username') or "").strip()
    p = (data.get('password') or "").strip()
    if not u or not p:
        return jsonify({"ok": False, "error": "username and password required"}), 400
    ok, msg = create_user(u, p)
    return jsonify({"ok": ok, "message": msg})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    u = (data.get('username') or "").strip()
    p = (data.get('password') or "").strip()
    if not u or not p:
        return jsonify({"ok": False, "error": "username and password required"}), 400
    ok, msg = verify_user(u, p)
    return jsonify({"ok": ok, "message": msg})

# Optional backend TTS
@app.route('/api/say', methods=['POST'])
def api_say():
    data = request.get_json() or {}
    text = (data.get('text') or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400
    speak_text_async(text)
    return jsonify({"ok": True, "text": "speaking"})

# ========================
# START SERVER
# ========================
if __name__ == '__main__':
    speak_text_async("NOVA is ready.")  # Startup message
    app.run(host="127.0.0.1", port=PORT, debug=False)
