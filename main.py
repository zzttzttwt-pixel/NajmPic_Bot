import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from telegram.error import BadRequest
from telegram.request import HTTPXRequest

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# جلب التوكن ومفتاح الذكاء الاصطناعي من السيرفر
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ⚠️ ضع هنا معرف قناتك (مثال: @my_channel)
CHANNEL_USERNAME = "@ضع_معرف_قناتك_هنا" 

# تشغيل مكتبة Gemini المحدثة
client = genai.Client(api_key=GEMINI_API_KEY)

# دالة للتحقق من الاشتراك الإجباري
async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except BadRequest:
        return False

# دالة الترحيب /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_subscribed(user_id, context):
        welcome_text = (
            "🤖 أهلاً بك في بوت الذكاء الاصطناعي الشامل المطور!\n\n"
            "💬 **للمحادثة العادية:** أرسل لي أي سؤال وسأجيبك فوراً.\n"
            "🎨 **لتوليد الصور:** اكتب الأمر `/draw` متبوعاً بالوصف، أو ابدأ رسالتك بكلمة **ارسم**.\n"
            "💡 *مثال:* `ارسم سيارة رياضية فاخرة في شوارع مكة`"
        )
        await update.message.reply_text(welcome_text)
    else:
        keyboard = [
            [InlineKeyboardButton("اضغط هنا للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("تفعيل البوت بعد الاشتراك 🔄", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"عذراً يا أخي، يجب عليك الاشتراك في قناتنا أولاً لتتمكن من استخدام البوت وميزاته مجاناً!\n\nاشترك ثم اضغط على زر التفعيل بالأسفل 👇", reply_markup=reply_markup)

# دالة السحرية لتوليد الصور وإرسالها حقيقية
async def generate_and_send_image(chat_id, prompt, update, context, waiting_message):
    try:
        # تحويل النص لرابط صورة مباشر ومضمون 100% عبر Pollinations AI
        formatted_prompt = prompt.strip().replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/{formatted_prompt}?width=1024&height=1024&nologo=true"
        
        # إرسال الصورة للمستخدم مباشرة كملف صورة حقيقي
        await context.bot.send_photo(
            chat_id=chat_id, 
            photo=image_url, 
            caption=f"✨ صورتك الجاهزة بناءً على طلبك:\n`{prompt}`", 
            parse_mode="Markdown"
        )
        await waiting_message.delete()
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        await waiting_message.edit_text("عذراً، حدث خطأ أثناء توليد الصورة، يرجى المحاولة مجدداً.")

# دالة معالجة الأوامر المباشرة /draw و /img
async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        return
    
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("يرجى كتابة وصف للصورة بعد الأمر. مثال: `/draw سيارة حديثة`")
        return
        
    waiting_message = await update.message.reply_text("جاري تخيل وصنع صورتك الآن... انتظر ثوانٍ 🎨⏳")
    await generate_and_send_image(update.effective_chat.id, prompt, update, context, waiting_message)

# دالة الرد على الرسائل النصية العادية والذكية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    if not await is_subscribed(user_id, context):
        keyboard = [[InlineKeyboardButton("اضغط هنا للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        await update.message.reply_text("عذراً، يرجى الاشتراك في القناة أولاً لتتمكن من استخدام البوت!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ✨ الحيلة الذكية: إذا بدأ المستخدم كلامه بكلمة "ارسم" أو "صورة"
    if user_text.strip().startswith(("ارسم", "صورة", "draw", "img")):
        # حذف كلمة "ارسم" من الوصف وإرسالها لمحرك الصور فوراً
        clean_prompt = user_text.replace("ارسم", "").replace("صورة", "").strip()
        if clean_prompt:
            waiting_message = await update.message.reply_text("فهمتك! جاري رسم وتوليد صورتك الآن... 🎨⏳")
            await generate_and_send_image(update.effective_chat.id, clean_prompt, update, context, waiting_message)
            return

    # المحادثة النصية العادية مع Gemini
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error calling Gemini API: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء معالجة طلبك.")

# بناء وتجهيز تطبيق تليجرام مع حل مشكلة الـ Timeout
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("خطأ: TELEGRAM_BOT_TOKEN غير موجود!")

torrent_request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(torrent_request).build()

# إضافة الأوامر والمستقبلات
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler(["draw", "img"], draw_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# تشغيل البوت
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(application.run_polling())
