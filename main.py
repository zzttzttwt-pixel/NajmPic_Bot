import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from telegram.error import BadRequest

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# جلب التوكن ومفتاح الذكاء الاصطناعي من السيرفر
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ⚠️ ضع هنا معرف قناتك الجديد (مثال: @my_channel)
CHANNEL_USERNAME = "@https://t.me/+y30XSIXPqlQyZDBk" 

# تشغيل مكتبة Gemini المحدثة
client = genai.Client(api_key=GEMINI_API_KEY)

# دالة للتحقق من الاشتراك الإجباري في القناة
async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except BadRequest:
        return False

# دالة الترحيب /start وتشرح للمستخدم كيف يرسم
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if await is_subscribed(user_id, context):
        welcome_text = (
            "🤖 أهلاً بك في بوت الذكاء الاصطناعي المتطور الجديد!\n\n"
            "💬 **للمحادثة العادية:** أرسل لي أي سؤال وسأجيبك فوراً.\n"
            "🎨 **لتوليد الصور:** اكتب الأمر `/draw` أو `/img` متبوعاً بالوصف الذي تريده.\n"
            "💡 *مثال:* `/draw لوحة سينمائية لسيارة رياضية فاخرة تحت المطر`"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
    else:
        keyboard = [
            [InlineKeyboardButton("اضغط هنا للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("تفعيل البوت بعد الاشتراك 🔄", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"عذراً يا أخي، يجب عليك الاشتراك في قناتنا أولاً لتتمكن من استخدام البوت وميزاته مجاناً!\n\nاشترك ثم اضغط على زر التفعيل بالأسفل 👇",
            reply_markup=reply_markup
        )

# دالة مخصصة لتوليد الصور عند استخدام الأوامر /draw أو /img
async def draw_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # التحقق من الاشتراك أولاً
    if not await is_subscribed(user_id, context):
        keyboard = [[InlineKeyboardButton("اضغط هنا للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        await update.message.reply_text("يرجى الاشتراك في القناة أولاً لتفعيل ميزة رسم الصور!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # جلب الوصف المكتوب بعد الأمر
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("يرجى كتابة وصف للصورة بعد الأمر.\nمثال: `/draw سيارة حديثة سريعة`", parse_mode="Markdown")
        return

    waiting_message = await update.message.reply_text("جاري تخيل وصنع صورتك الآن بدقة عالية... انتظر ثوانٍ 🎨⏳")

    try:
        # استخدام موديل توليد الصور الحديث من جوجل Imagen 3
        result = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                aspect_ratio="1:1",
                output_mime_type="image/jpeg"
            )
        )
        
        # جلب الصورة من الرد وإرسالها للمستخدم
        for generated_image in result.generated_images:
            image_bytes = generated_image.image.image_bytes
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=f"✨ صورتك الجاهزة بناءً على طلبك:\n`{prompt}`", parse_mode="Markdown")
            
        await waiting_message.delete() # حذف رسالة الانتظار
        
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        await waiting_message.edit_text("عذراً، حدث خطأ أثناء توليد الصورة. تأكد من أن الوصف لا يخالف سياسات المحتوى المحظور.")

# دالة الرد على الرسائل النصية العادية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    if not await is_subscribed(user_id, context):
        keyboard = [[InlineKeyboardButton("اضغط هنا للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        await update.message.reply_text("عذراً، يرجى الاشتراك في القناة أولاً لتتمكن من استخدام البوت!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error calling Gemini API: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء معالجة طلبك.")

# بناء وتجهيز تطبيق تليجرام الجديد
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("خطأ: TELEGRAM_BOT_TOKEN غير موجود!")

application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# إضافة الأوامر والمستقبلات
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler(["draw", "img"], draw_image)) # تفريغ أوامر الصور
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# تشغيل البوت
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(application.run_polling())
