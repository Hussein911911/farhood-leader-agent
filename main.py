import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
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

# === ربط OpenRouter API ===
ai_client = None
if OPENROUTER_API_KEY:
    ai_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

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

# === النماذج الذكية المخصصة للأيجنتس ===
AGENT_MODELS = {
    "Leader": "openai/gpt-4o",
    "Dev": "anthropic/claude-3.5-sonnet",
    "Media": "google/gemini-flash-1.5",
    "Publisher": "deepseek/deepseek-chat"
}

def call_ai_agent(model_name: str, system_prompt: str, user_prompt: str) -> str:
    if not ai_client:
        return "❌ خطأ: لم يتم إضافة مفتاح OPENROUTER_API_KEY في إعدادات Render."
    try:
        response = ai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            extra_headers={
                "HTTP-Referer": "https://farhood-agents.com",
                "X-Title": "Farhood Agent Swarm",
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ خطأ أثناء الاتصال بالنموذج ({model_name}): {str(e)}"

# === أوامر البوت ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 أهلاً بك في شبكة Farhood Agents العملاقة!\n\n"
        "تم ربط البوت بأقوى نماذج الذكاء الاصطناعي العالمية:\n"
        "• 🧠 Leader Agent: يُدار بـ GPT-4o (التخطيط والتحليل)\n"
        "• 💻 Dev Agent: يُدار بـ Claude 3.5 Sonnet (البرمجة والتطوير)\n"
        "• 🎨 Media Agent: يُدار بـ Gemini 1.5 (المحتوى والتصميم)\n"
        "• 📡 Publisher Agent: يُدار بـ DeepSeek (الأتمتة والمعالجة)\n\n"
        "اكتب لي أي أمر بلغة طبيعية وسيقوم الفريق بالعمل فوراً!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    status_msg = await update.message.reply_text("🧠 Leader Agent (GPT-4o) يحلل طلبك ويكلف الفريق...")

    # 1. القائد (GPT-4o) يحلل الطلب
    leader_prompt = "أنت القائد المباشر لشبكة أيجنتس ذكاء اصطناعي. قم بتحليل طلب المستخدم وتفكيكه إلى خطوات عملية مخصصة للمطور والميديا مع توجيه واضح بأسلوب احترافي باللغة العربية."
    leader_plan = call_ai_agent(AGENT_MODELS["Leader"], leader_prompt, user_input)

    await status_msg.edit_text("💻 Dev Agent (Claude 3.5 Sonnet) يبني الأكواد والحل التقني...")

    # 2. المطور (Claude 3.5 Sonnet) ينفذ الكود
    dev_prompt = "أنت خبير البرمجة والتطوير (Dev Agent). قم بكتابة الأكواد والحلول التقنية المطلوبة وفقاً لخطة القائد بأعلى جودة وبشكل مكتمل."
    dev_output = call_ai_agent(AGENT_MODELS["Dev"], dev_prompt, f"طلب المستخدم: {user_input}\nخطة القائد: {leader_plan}")

    # التقرير النهائي
    final_output = (
        f"📋 خطة القائد (GPT-4o):\n{leader_plan}\n\n"
        f"⚙️ ==============================\n\n"
        f"💻 تنفيذ المطور (Claude 3.5 Sonnet):\n{dev_output}"
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

    # إرسال النتيجة (تقسيم الرسالة إذا كانت طويلة جداً)
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
    
