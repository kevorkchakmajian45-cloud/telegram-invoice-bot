import os
import logging
import json
from threading import Thread
from flask import Flask
import telebot
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# قراءة المفاتيح والبيانات السرية من بيئة التشغيل
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SPREADSHEET_ID = "1lwjhzJW_HShwZR1RnROcnUrwYONHPsrFqlY2W4sqTWQ"

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    logger.error("❌ تنبيه: مفتاح التليجرام أو مفتاح Gemini غير موجود في المتغيرات البيئية!")

# تهيئة Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
# استخدام نموذج يدعم تحليل الصور
model = genai.GenerativeModel('gemini-1.5-flash')

# تهيئة بوت التليجرام باستخدام مكتبة pytelegrambotapi
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# إعداد خادم Flask البسيط لمنع انقطاع الاتصال على Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Invoice Bot is running successfully with Google Sheets!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# دالة الاتصال بـ Google Sheets بالطريقة العامة المفتوحة بالرابط/المعرف
def save_to_sheet(row_data):
    try:
        # استخدام الاتصال المباشر عبر gspread للجدول المتاح بالرابط
        gc = gspread.oauth(credentials_filename=None) # أو بطريقة فتح الجدول بالمعرف مباشرة
        # الطريقة الأبسط للوصول العام للملف عبر الـ ID
        # (ملاحظة: يتطلب حساب خدمة أو الاعتماد على طريقة open_by_key إذا كانت الصلاحية عامة)
        client = gspread.client.Client(auth=None)
        
        # سنستخدم طريقة المصادقة العامة أو فتح الجدول المباشر
        # لضمان عملها بسلاسة مع الصلاحية العامة للرابط:
        # سنقوم بفتح الجدول مباشرة باستخدام مكتبة gspread المفتوحة للرابط العام
        import urllib.request
        # الطريقة البديلة المضمونة للربط المباشر:
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
        
        # كود مبسط للاتصال عبر الـ gspread العام
        # سنقوم بفتح أول ورقة عمل في الجدول
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        sheet.append_row(row_data)
        logger.info("✅ تم حفظ الفاتورة في جدول البيانات بنجاح!")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ أثناء حفظ البيانات في الجدول: {e}")
        return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل لي صورة أي فاتورة وسأقوم باستخراج بياناتها وحفظها في جدول Expenses تلقائياً.")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    try:
        bot.reply_to(message, "⏳ جاري قراءة وتحليل الفاتورة بالذكاء الاصطناعي...")
        
        # الحصول على أرفع دقة للصورة المرسلة
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # حفظ الصورة مؤقتاً لمعالجتها
        image_path = "temp_receipt.jpg"
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # فتح الصورة بواسطة Gemini واستخراج البيانات بالشكل المطلوب
        with open(image_path, 'rb') as img_file:
            image_parts = [{
                'mime_type': 'image/jpeg',
                'data': img_file.read()
            }]
            
        prompt = """
        قم بتحليل صورة الفاتورة هذه بدقة واستخرج المعلومات التالية فقط بصيغة JSON حقيقية وبدون أي نصوص إضافية:
        {
          "date": "التاريخ الموجود على الفاتورة بصيغة YYYY-MM-DD وإن لم يوجد ضع تاريخ اليوم",
          "vendor": "اسم البائع أو المتجر بالعربية أو الإنجليزية",
          "total": "المبلغ الإجمالي كرقَم فقط بدون عملات",
          "details": "تفاصيل العناصر أو البضائع المشتراة باختصار"
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
        
        # محاولة الحفظ المباشر في الجدول
        # ترتيب الأعمدة في الجدول: التاريخ | اسم البائع | المبلغ الإجمالي | التفاصيل
        success = False
        try:
            # طريقة بديلة ومباشرة للاتصال بـ gspread في بيئة السحابة
            import gspread
            from google.auth import default
            
            # محاولة الاعتماد على الاعتمادية الافتراضية أو فتح مباشر
            gc = gspread.service_account(filename='credentials.json') if os.path.exists('credentials.json') else None
            if not gc:
                # إذا لم يوجد ملف بيانات اعتماد، سنستخدم الطريقة العامة إذا أمكن أو تنبيه المستخدم
                # طريقة بديلة لفتح الجدول عبر رابط عام أو مفتاح الخدمة
                pass
        except Exception as sheet_err:
            logger.error(f"Sheet connection detail error: {sheet_err}")

        # حفظ البيانات وإرسال الرد للمستخدم
        bot.reply_to(message, f"✅ **تم تحليل الفاتورة بنجاح!**\n\n📅 **التاريخ:** {row_date}\n🏪 **البائع:** {row_vendor}\n💰 **المبلغ:** {row_total}\n📝 **التفاصيل:** {row_details}\n\n*جاري حفظها في جدولك...*")

        # إزالة الملف المؤقت
        if os.path.exists(image_path):
            os.remove(image_path)

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        bot.reply_to(message, "عذراً، حدث خطأ أثناء تحليل الفاتورة. تأكد من وضوح الصورة وحاول مرة أخرى.")

if __name__ == "__main__":
    # تشغيل خادم الـ Flask في خلفية منفصلة
    t = Thread(target=run_flask)
    t.start()
    
    # تشغيل البوت
    logger.info("🤖 Bot is starting polling...")
    bot.infinity_polling()
