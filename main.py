import os
import requests
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# -------------------------------------------------------------
# 1. إعداد المفاتيح والمتغيرات
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8786093994:AAFNzshAFEic2Ci7TF8Btu4O67iPgNAT5qw"
SUPABASE_URL = "https://oscramduvfzacfnncakx.supabase.co"
SUPABASE_KEYeyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9zY3JhbWR1dmZ6YWNmbm5jYWt4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ3ODgwMDMsImV4cCI6MjEwMDM2NDAwM30.XJsqrAw5l9A_MLbQRV64fYMDNy3_N1aN5D-6N86s7F8

# تهيئة البوت
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ترويسات الاتصال بـ Supabase REST API
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# -------------------------------------------------------------
# 2. وظائف الاتصال بقاعدة البيانات (Supabase Helpers)
# -------------------------------------------------------------
def get_available_agents():
    """جلب قائمة الأيجنتس المسجلين من Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/agents?select=*"
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def create_task_in_db(title, agent_id, payload, requires_approval=True):
    """إضافة مهمة جديدة إلى طابور المهام"""
    url = f"{SUPABASE_URL}/rest/v1/tasks_queue"
    data = {
        "title": title,
        "assigned_agent_id": agent_id,
        "status": "pending_approval" if requires_approval else "running",
        "payload": payload,
        "requires_approval": requires_approval
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json() if response.status_code in [200, 201] else None

def update_task_status(task_id, approved: bool):
    """تحديث حالة المهمة بعد موافقة أو رفض المستخدم"""
    url = f"{SUPABASE_URL}/rest/v1/tasks_queue?id=eq.{task_id}"
    status = "running" if approved else "cancelled"
    data = {
        "status": status,
        "approved_by_user": approved
    }
    requests.patch(url, headers=headers, json=data)

# -------------------------------------------------------------
# 3. معالجة الرسائل الواردة من المستخدم (Leader Processing)
# -------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    agents = get_available_agents()
    agent_names = ", ".join([a['name'] for a in agents]) if agents else "جاري التحميل..."
    
    welcome_text = (
        "🤖 **أهلاً بك! أنا الأيجنت القائد (Leader Agent)**\n\n"
        "أنا جاهز لاستلام أوامرك وتوجيه الفريق المتخصص.\n"
        f"📋 **الفريق المتاح حالياً:** {agent_names}\n\n"
        "اكتب لي طلبك بلغة طبيعية وسأقوم بتفكيكه ووضع خطة التنفيذ!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_user_request(message):
    user_prompt = message.text
    chat_id = message.chat.id
    
    bot.send_message(chat_id, "⏳ **جاري تحليل الطلب واستدعاء الأيجنتس المناسبين...**")
    
    # جلب الأيجنتس
    agents = get_available_agents()
    
    # إنشاء خطة مبسطة كمثال للتأكيد (يمكن ربطها بـ OpenAI/Gemini هنا للصياغة الذكية)
    plan_summary = (
        f"🎯 **خطة التنفيذ المقترحة للطلب:**\n\"{user_prompt}\"\n\n"
        "1. 🛠️ **Dev Agent:** بناء الهيكل الأساسي للبرمجيات/الموقع.\n"
        "2. 🎨 **Media Agent:** صياغة وتوليد الوسائط والصور المطلوب.\n"
        "3. 📢 **Publisher Agent:** إعداد خطة النشر والجدولة.\n\n"
        "⚠️ **ملاحظة:** لن يتم النشر أو الاعتماد النهائي إلا بعد تأكيدك."
    )
    
    # حفظ المهمة الرئيسية في Supabase
    dev_agent = next((a for a in agents if a['name'] == 'Dev Agent'), None)
    agent_id = dev_agent['id'] if dev_agent else None
    
    task_res = create_task_in_db(
        title=f"طلب: {user_prompt[:30]}...",
        agent_id=agent_id,
        payload={"raw_prompt": user_prompt}
    )
    
    task_id = task_res[0]['id'] if task_res else "temp_id"

    # إنشاء أزرار الموافقة البشرية (Human-in-the-Loop)
    markup = InlineKeyboardMarkup()
    btn_approve = InlineKeyboardButton("✅ موافقة وتنفيذ", callback_data=f"approve_{task_id}")
    btn_edit = InlineKeyboardButton("✏️ تعديل الخطة", callback_data=f"edit_{task_id}")
    btn_cancel = InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{task_id}")
    markup.add(btn_approve, btn_edit)
    markup.add(btn_cancel)

    bot.send_message(chat_id, plan_summary, reply_markup=markup, parse_mode="Markdown")

# -------------------------------------------------------------
# 4. معالجة ضغطات الأزرار (Approvals Callback)
# -------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data.startswith("approve_"):
        task_id = data.split("_")[1]
        update_task_status(task_id, approved=True)
        bot.answer_callback_query(call.id, "تمت الموافقة!")
        bot.edit_message_text(
            f"✅ **تمت الموافقة بنجاح!**\nبدأ الأيجنتس بالعمل على المهمة الآن...", 
            chat_id=chat_id, 
            message_id=call.message.message_id
        )
        
    elif data.startswith("cancel_"):
        task_id = data.split("_")[1]
        update_task_status(task_id, approved=False)
        bot.answer_callback_query(call.id, "تم الإلغاء")
        bot.edit_message_text(
            "❌ **تم إلغاء المهمة بنجاح.**", 
            chat_id=chat_id, 
            message_id=call.message.message_id
        )
        
    elif data.startswith("edit_"):
        bot.answer_callback_query(call.id, "يرجى كتابة التعديل")
        bot.send_message(chat_id, "✍️ اكتب التعديلات التي تريد إضافتها على الخطة:")

# -------------------------------------------------------------
# 5. تشغيل المحرك
# -------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Leader Agent is running and listening to Telegram...")
    bot.infinity_polling()
