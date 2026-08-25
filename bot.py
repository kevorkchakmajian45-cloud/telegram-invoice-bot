import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai

# إعداد السجلات (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# قراءة المفاتيح من البيئة
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    logger.error("❌ تحذير: أحد المفاتيح (Token أو API Key) غير موجود في المتغيرات البيئية!")

# تهيئة عميل Gemini الجديد
client = genai.Client(api_key=GOOGLE_API_KEY)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    await update.message.reply_text("⏳ جاري تحليل الفاتورة وتنظيم البيانات...")

    try:
        # استخدام نموذج Gemini لتنظيم بيانات الفاتورة
        prompt = f"""
        قم بتحليل النص التالي المستخرج من الفاتورة واستخرج المعلومات الأساسية بشكل منظم وواضح (مثل: اسم البائع، المبلغ الإجمالي، التاريخ، العناصر أو الخدمات، ورقم الفاتورة إن وجد).
        
        نص الفاتورة:
        {user_text}
        """
        
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة الفاتورة عبر الذكاء الاصطناعي.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # الرد على أي رسالة نصية تحتوي على تفاصيل الفاتورة
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 Bot is running and waiting for invoices...")
    application.run_polling()

if __name__ == '__main__':
    main()
