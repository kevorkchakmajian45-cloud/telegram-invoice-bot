import os
import logging
import json
from flask import Flask, request
import telebot
import google.generativeai as genai
from PIL import Image
import io

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# قراءة المفاتيح
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# تهيئة Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# تهيئة بوت التليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# إعداد خادم Flask للعمل كـ Web Service على Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Invoice Bot is running successfully!"

# استقبال التحديثات من تليجرام عبر Webhook لتجنب مشاكل الـ Timeout
@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def receive_update():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل لي صورة الفاتورة وسأقوم باستخراج بياناتها بدقة.")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    try:
        bot.reply_to(message, "⏳ جاري قراءة وتحليل الفاتورة بالذكاء الاصطناعي...")
        
        # تحميل الصورة المرسلة مباشرة إلى الذاكرة
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        image = Image.open(io.BytesIO(downloaded_file))
        
        prompt = """
        قم بتحليل صورة الفاتورة هذه بدقة واستخرج المعلومات التالية فقط بصيغة JSON صريحة وبدون أي نصوص إضافية أو علامات ماركداون:
        {
          "date": "التاريخ الموجود على الفاتورة بصيغة YYYY-MM-DD",
          "vendor": "اسم المتجر أو البائع",
          "total": "المبلغ الإجمالي كرقَم فقط مثل 53.54",
          "details": "أبرز العناصر المشتراة باختصار"
        }
        """
        
        response = model.generate_content([prompt, image])
        text_result = response.text.strip()
        
        if text_result.startswith("```json"):
            text_result = text_result[7:]
        if text_result.endswith("```"):
            text_result = text_result[:-3]
            
        data = json.loads(text_result.strip())
        
        row_date = data.get("date", "غير متوفر")
        row_vendor = data.get("vendor", "غير متوفر")
        row_total = data.get("total", "غير متوفر")
        row_details = data.get("details", "غير متوفر")
        
        bot.reply_to(message, f"✅ **تم تحليل الفاتورة بنجاح!**\n\n📅 **التاريخ:** {row_date}\n🏪 **البائع:** {row_vendor}\n💰 **المبلغ:** {row_total}\n📝 **التفاصيل:** {row_details}")

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        bot.reply_to(message, f"عذراً، حدث خطأ أثناء تحليل الفاتورة: {str(e)}")

if __name__ == "__main__":
    # تعيين الـ Webhook تلقائياً عند بدء التشغيل
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if RENDER_EXTERNAL_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{TELEGRAM_BOT_TOKEN}")
        logger.info(f"Webhook set to {RENDER_EXTERNAL_URL}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
