import os
import logging
import json
from threading import Thread
from flask import Flask
import telebot
import google.generativeai as genai

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

# إعداد خادم Flask البسيط لـ Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Invoice Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل لي صورة الفاتورة وسأقوم باستخراج بياناتها بدقة.")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    image_path = "temp_receipt.jpg"
    try:
        bot.reply_to(message, "⏳ جاري قراءة وتحليل الفاتورة بالذكاء الاصطناعي...")
        
        # تحميل الصورة المرسلة
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # رفع الصورة باستخدام ميزة الملفات في GenAI
        sample_file = genai.upload_file(image_path, mime_type="image/jpeg")
        
        prompt = """
        قم بتحليل صورة الفاتورة هذه بدقة واستخرج المعلومات التالية فقط بصيغة JSON صريحة وبدون أي نصوص إضافية أو علامات ماركداون:
        {
          "date": "التاريخ الموجود على الفاتورة بصيغة YYYY-MM-DD",
          "vendor": "اسم المتجر أو البائع",
          "total": "المبلغ الإجمالي كرقَم فقط مثل 53.54",
          "details": "أبرز العناصر المشتراة باختصار"
        }
        """
        
        response = model.generate_content([sample_file, prompt])
        text_result = response.text.strip()
        
        # تنظيف الرد للحصول على JSON سليم
        if text_result.startswith("```json"):
            text_result = text_result[7:]
        if text_result.endswith("```"):
            text_result = text_result[:-3]
            
        data = json.loads(text_result.strip())
        
        row_date = data.get("date", "غير متوفر")
        row_vendor = data.get("vendor", "غير متوفر")
        row_total = data.get("total", "غير متوفر")
        row_details = data.get("details", "غير متوفر")
        
        # إرسال النتيجة للمستخدم
        bot.reply_to(message, f"✅ **تم تحليل الفاتورة بنجاح!**\n\n📅 **التاريخ:** {row_date}\n🏪 **البائع:** {row_vendor}\n💰 **المبلغ:** {row_total}\n📝 **التفاصيل:** {row_details}")

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        bot.reply_to(message, "عذراً، حدث خطأ أثناء تحليل الفاتورة. تأكد من وضوح الصورة وحاول مرة أخرى.")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    logger.info("🤖 Bot is starting polling...")
    bot.infinity_polling()
