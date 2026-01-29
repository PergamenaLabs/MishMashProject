import os
import sqlite3
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memory.db")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")

# API Anahtarı (Ortam Değişkeninden)
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
MODEL_NAME = "gemini-2.0-flash"

# --- GİZLİ VERİTABANI (ARŞİV) ---
def init_db():
    """Veritabanını ve tabloyu oluşturur."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_to_archive(role, message):
    """
    Mesajları 'memory.db' dosyasına yazar.
    Bu dosyaya web üzerinden ERİŞİLEMEZ.
    Sadece Codespaces dosya yöneticisinden görülebilir.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO conversations (role, message) VALUES (?, ?)", (role, message))
    except Exception as e:
        print(f"Arşiv Hatası: {e}")

def load_short_term_memory(limit=10):
    """Botun sohbeti sürdürebilmesi için son mesajları çeker."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, message FROM conversations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return list(reversed(rows))
    except:
        return []

def load_knowledge_base():
    """Knowledge klasöründeki txt dosyalarını okur."""
    text = ""
    if os.path.exists(KNOWLEDGE_DIR):
        for f in os.listdir(KNOWLEDGE_DIR):
            if f.endswith(".txt"):
                with open(os.path.join(KNOWLEDGE_DIR, f), "r", encoding="utf-8") as file:
                    text += f"\n--- {f} ---\n{file.read()}\n"
    return text

# Botun Kişiliği ve Bilgisi
SYSTEM_PROMPT = f"""
You are Muse-Bot, Cansel Tosun's AI assistant.
KNOWLEDGE BASE:
{load_knowledge_base()}
INSTRUCTIONS:
- Be helpful and concise.
- Reply in the user's language.
"""

# Başlangıçta DB kontrolü yap
init_db()

# --- SADECE 2 ADET KAPIMIZ VAR ---

# 1. KAPI: Siteyi Göster (Splash Screen)
@app.route('/')
def home():
    return render_template('index.html')

# 2. KAPI: Sohbet Et
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message')
        if not user_message: return jsonify({"error": "Empty"}), 400

        # A) Kullanıcıyı Arşivle
        save_to_archive("user", user_message)

        # B) Hafızayı Yükle
        history = load_short_term_memory()
        gemini_content = []
        for row in history:
            role = "model" if row["role"] == "assistant" else "user"
            gemini_content.append(types.Content(role=role, parts=[types.Part(text=row["message"])]))

        # C) Gemini'ye Sor
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=gemini_content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7
            )
        )
        bot_reply = response.text

        # D) Bot Cevabını Arşivle
        save_to_archive("assistant", bot_reply)

        return jsonify({"reply": bot_reply})

    except Exception as e:
        return jsonify({"reply": "Error occurred."}), 500

if __name__ == '__main__':
    # 8080 portunda çalışır
    app.run(host='0.0.0.0', port=8080)