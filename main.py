import os
import json
import requests
import threading
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

# === قائمة النماذج المجانية المستقرة والواسعة ===
FREE_MODELS_POOL = [
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "openchat/openchat-7b:free",
    "gryphe/mythomax-l2-13b:free"
]

# === دالة الذكاء الاصطناعي مع كاشف أخطاء تفصيلي ===
def call_ai_agent_smart(system_prompt: str, user_prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        return "❌ خطأ: لم يتم إضافة مفتاح OPENROUTER_API_KEY في إعدادات Render."
    
    clean_key = "".join(OPENROUTER_API_KEY.split())
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://farhood-agents.com",
        "X-Title": "Farhood Agent Swarm"
    }
    
    last_error_details = ""

    # تجربة النماذج واحداً تلو الآخر
    for model in FREE_MODELS_POOL:
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
            else:
                if "error" in res_data:
                    last_error_details = f"[{model}]: {res_data['error'].get('message', '')}"
                else:
                    last_error_details = f"[{model}]: Status Code {response.status_code}"
        except Exception as e:
            last_error_details = f"[{model}]: {str(e)}"
            continue

    return f"⚠️ فشلت المحاولات مع النماذج المجانية.\nآخر تفاصيل للخطأ: {last_error_details}"

# === أوامر البوت ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 أهلاً بك في شبكة Farhood Agents العملاقة!\n\n"
        "الشبكة تعمل بنظام (Auto-Fallback) مع 7 نماذج ذكاء مجانية سريعة.\n\n"
        "اكتب لي أي طلب وسيقوم الفريق بالتحليل والتنفيذ فوراً!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    status_msg = await update.message.reply_text("🧠 Leader Agent يحلل طلبك ويكلف الفريق...")

    # 1. القائد يحلل الطلب
    leader_prompt = "أنت القائد المباشر لشبكة أيجنتس ذكاء اصطناعي. قم بتحليل طلب المستخدم وتفكيكه إلى خطوات عملية مخصصة للمطور والميديا مع توجيه واضح بأسلوب احترافي باللغة العربية."
    leader_plan = call_ai_agent_smart(leader_prompt, user_input)

    await status_msg.edit_text("💻 Dev Agent يبني الأكواد والحل التقني...")

    # 2. المطور ينفذ الكود
    dev_prompt = "أنت خبير البرمجة والتطوير (Dev Agent). قم بكتابة الأكواد والحلول التقنية المطلوبة وفقاً لخطة القائد بأعلى جودة وبشكل مكتمل."
    dev_output = call_ai_agent_smart(dev_prompt, f"طلب المستخدم: {user_input}\nخطة القائد: {leader_plan}")

    # التقرير النهائي
    final_output = (
        f"📋 خطة القائد:\n{leader_plan}\n\n"
        f"⚙️ ==============================\n\n"
        f"💻 تنفيذ المطور:\n{dev_output}"
    )

    # حفظ السجل في Supabase
    if supabase:
        try:
            supabase.table("agent_logs").insert({
                "user_id": str(update.effective_user.id),
                "prompt": user_input,
                "response": final_output
            }).execute()
        except Exception as e:
            print(f"Supabase Log Error: {e}")

    # إرسال النتيجة
    if len(final_output) > 4000:
        await status_msg.delete()
        for i in range(0, len(final_output), 4000):
            await update.message.reply_text(final_output[i:i+4000])
    else:
        await status_msg.edit_text(final_output)

def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Swarm Engine is Live...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
