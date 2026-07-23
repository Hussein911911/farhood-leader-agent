import os
import json
import requests
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client

# === المتغيرات البيئية ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# === ربط Supabase ===
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Connection Error: {e}")

# === سيرفر الاستمرارية مجاناً 24/7 على Render (Health Check) ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Farhood AI Swarm Live")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# === دالة جلب النماذج المجانية المتاحة حياً ===
def get_live_free_models():
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if res.status_code == 200:
            data = res.json().get("data", [])
            free_models = [m["id"] for m in data if ":free" in m["id"]]
            if free_models:
                return free_models
    except Exception as e:
        print(f"Error fetching live models: {e}")
    
    return [
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-coder-32b-instruct:free"
    ]

# === دالة الذكاء الاصطناعي السريعة ===
def call_ai_agent_smart(system_prompt: str, user_prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        return "❌ خطأ: لم يتم إضافة مفتاح OPENROUTER_API_KEY."
    
    clean_key = "".join(OPENROUTER_API_KEY.split())
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://farhood-agents.com",
        "X-Title": "Farhood Agent Swarm"
    }
    
    live_models = get_live_free_models()

    for model in live_models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            res_data = response.json()
            if response.status_code == 200 and "choices" in res_data:
                return res_data["choices"][0]["message"]["content"]
        except Exception:
            continue

    return "⚠️ جميع النماذج المجانية مشغولة حالياً."

# === أوامر البوت ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 أهلاً بك في شبكة Farhood Agents السريعة!\n\n"
        "• اطلب أي صورة (مثال: 'صورة وردة بنفسجية') وسأولدها لك فوراً 🎨\n"
        "• اطلب أي كود أو استفسار برلمجي وسيجيبك المطور باختصار ودقة 💻"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    image_keywords = ["صورة", "صوره", "ارسم", "صمم", "توليد صورة", "image", "draw", "picture"]
    
    # 🎨 إذا كان الطلب صورة: قم بتوليدها وإرسالها مباشرة!
    if any(keyword in user_input.lower() for keyword in image_keywords):
        status_msg = await update.message.reply_text("🎨 جاري رسم وتوليد الصورة فوراً...")
        try:
            # ترجمة وصياغة الوصف بالإنجليزية سريعة
            prompt_en = call_ai_agent_smart(
                "Translate and convert the user's image request into a high quality English image prompt. Return ONLY the prompt string, nothing else.",
                user_input
            )
            
            # توليد رابط الصورة المباشر مجاناً
            encoded_prompt = urllib.parse.quote(prompt_en)
            image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
            
            await update.message.reply_photo(photo=image_url, caption=f"🖼️ الصورة المطلوبة بناءً على طلبك:\n*{user_input}*")
            await status_msg.delete()
            return
        except Exception as e:
            await status_msg.edit_text(f"❌ حدث خطأ أثناء إنشاء الصورة: {str(e)}")
            return

    # 💻 للطلبات البرمجية والتحليليّة: إجابة مباشرة ومختصرة بدون إنشاء تقارير عملاقة
    status_msg = await update.message.reply_text("⚡ جاري معالجة طلبك...")
    sys_prompt = "أنت خبير برمجي وذكاء اصطناعي. أجب على طلب المستخدم بأسلوب مباشر، مختصر، واحترافي بدون تقارير طويلة أو مقدمات غير ضرورية."
    ai_response = call_ai_agent_smart(sys_prompt, user_input)

    # حفظ السجل
    if supabase:
        try:
            supabase.table("agent_logs").insert({
                "user_id": str(update.effective_user.id),
                "prompt": user_input,
                "response": ai_response
            }).execute()
        except Exception as e:
            print(f"Supabase Log Error: {e}")

    await status_msg.edit_text(ai_response)

def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Swarm Engine is Live...")
    app.run_polling()

if __name__ == "__main__":
    main()
            
