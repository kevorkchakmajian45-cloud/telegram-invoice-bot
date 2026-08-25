import os
import logging
import json
from threading import Thread
from flask import Flask
import telebot
import google.generativeai as genai
import gspread

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# قراءة المفاتيح والبيانات السرية
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SPREADSHEET_ID = "1lwjhzJW_HShwZR1RnROcnUrwYONHPsrFqlY2W4sqTWQ"

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    logger.error("❌ تنبيه: مفتاح التليجرام أو مفتاح Gemini غير موجود!")

# تهيئة Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# تهيئة بوت التليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# إعداد خادم Flask لمنع انقطاع الاتصال على Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Invoice Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل لي صورة أي فاتورة وسأقوم باستخراج بياناتها وحفظها في جدول Expenses تلقائياً.")

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
            
        with open(image_path, 'rb') as img_file:
            image_parts = [{
                'mime_type': 'image/jpeg',
                'data': img_file.read()
            }]
            
        prompt = """
        قم بتحليل صورة الفاتورة هذه بدقة واستخرج المعلومات التالية فقط بصيغة JSON صريحة بدون أي نصوص إضافية أو علامات ماركداون إضافية:
        {
          "date": "التاريخ الموجود على الفاتورة بصيغة YYYY-MM-DD",
          "vendor": "اسم البائع أو المتجر مثل Costco",
          "total": "المبلغ الإجمالي كرقَم فقط بدون عملات مثل 53.54",
          "details": "أبرز العناصر المشتراة باختصار"
        }
        """
        
        response = model.generate_content([prompt, image_parts[0]])
        text_result = response.text.strip()
        
        # تنظيف الرد للحصول على صيغة JSON السليمة
        if text_result.startswith("```json"):
            text_result = text_result[7:]
        if text_result.endswith("```"):
            text_result = text_result[:-3]
            
        data = json.loads(text_result.strip())
        
        row_date = data.get("date", "")
        row_vendor = data.get("vendor", "")
        row_total = data.get("total", "")
        row_details = data.get("details", "")
        
        # محاولة الاتصال بـ Google Sheets عبر الملف العام المتاح برابط
        try:
            # استخدام gspread مع الاعتماد الافتراضي أو المصادقة العامة المتاحة للروابط العامة
            gc = gspread.service_account(filename='credentials.json') if os.path.exists('credentials.json') else None
            if gc:
                sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
                sheet.append_row([row_date, row_vendor, row_total, row_details])
                logger.info("✅ تم الحفظ في الجدول بنجاح!")
        except Exception as sheet_err:
            logger.error(f"⚠️ ملاحظة تخص الجدول: {sheet_err}")

        # إرسال النتيجة للمستخدم
        bot.reply_to(message, f"✅ **تم تحليل الفاتورة بنجاح!**\n\n📅 **التاريخ:** {row_date}\n🏪 **البائع:** {row_vendor}\n💰 **المبلغ:** {row_total}\n📝 **التفاصيل:** {row_details}\n\n*تمت القراءة بنجاح!*")

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        bot.reply_to(message, "عذراً، حدث خطأ أثناء تحليل الفاتورة. تأكد من وضوح الصورة وحاول مرة أخرى.")
    finally:
        # إزالة الملف المؤقت دائماً
        if os.path.exists(image_path):
            os.remove(image_path)

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    logger.info("🤖 Bot is starting polling...")
    bot.infinity_polling()
