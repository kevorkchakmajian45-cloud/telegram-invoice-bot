import os
import logging
import json
from flask import Flask, request
import telebot
from google import genai
from google.genai import types
from PIL import Image
import io

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب المفاتيح من البيئة
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# تهيئة عميل Gemini الجديد
client = genai.Client(api_key=GOOGLE_API_KEY)

# تهيئة بوت التليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# إعداد خادم Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Invoice Bot is Active and Running!"

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل لي صورة الفاتورة وسأقوم باستخراج بياناتها بدقة.")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    try:
        bot.reply_to(message, "⏳ جاري قراءة وتحليل الفاتورة بالذكاء الاصطناعي...")
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded_file))
        
        prompt = """
        قم بتحليل صورة الفاتورة هذه بدقة واستخرج المعلومات التالية فقط بصيغة JSON صريحة وبدون أي علامات ماركداون:
        {
          "date": "التاريخ الموجود على الفاتورة بصيغة YYYY-MM-DD",
          "vendor": "اسم المتجر أو البائع",
          "total": "المبلغ الإجمالي كرقَم فقط مثل 53.54",
          "details": "أبرز العناصر المشتراة باختصار"
        }
        """
        
        # استخدام العميل الحديث لطلب التحليل
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        
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
        
        bot.reply_to(
            message, 
            f"✅ **تم تحليل الفاتورة بنجاح!**\n\n"
            f"📅 **التاريخ:** {row_date}\n"
            f"🏪 **البائع:** {row_vendor}\n"
            f"💰 **المبلغ:** {row_total}\n"
            f"📝 **التفاصيل:** {row_details}"
        )

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        bot.reply_to(message, f"عذراً، حدث خطأ أثناء تحليل الفاتورة: {str(e)}")

# ضبط الـ Webhook عند بدء التشغيل
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
else:
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if RENDER_EXTERNAL_URL and TELEGRAM_BOT_TOKEN:
        webhook_url = f"{RENDER_EXTERNAL_URL}/{TELEGRAM_BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
