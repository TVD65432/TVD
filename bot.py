import os, requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# =================== yt-dlp से डायरेक्ट लिंक निकालें ===================
def get_direct_link(url):
    """Terabox, DiskWala या किसी भी सपोर्टेड साइट से डायरेक्ट वीडियो URL लौटाएगा"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # पूरा डेटा चाहिए
        'force_generic_extractor': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # वीडियो फ़ॉर्मैट खोजें (सबसे अच्छा mp4)
            formats = info.get('formats', [])
            for fmt in formats:
                if fmt.get('ext') == 'mp4' and fmt.get('url'):
                    return fmt['url']
            # अगर mp4 नहीं, तो कोई भी वीडियो URL
            for fmt in formats:
                if fmt.get('url') and fmt.get('vcodec') != 'none':
                    return fmt['url']
            # आखिरी कोशिश: info में सीधा url
            return info.get('url')
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None

# =================== टेलीग्राम हैंडलर ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("नमस्ते! Terabox/DiskWala का शेयर लिंक भेजें। बॉट yt-dlp से असली वीडियो देगा।")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    direct = get_direct_link(url)
    if not direct:
        await update.message.reply_text("❌ डायरेक्ट वीडियो लिंक नहीं निकल सका। लिंक सही/पब्लिक है या नहीं, जाँचें।")
        return

    # फ़ाइल साइज़ चेक करें
    try:
        head = requests.head(direct, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        file_size = int(head.headers.get('content-length', 0))
    except:
        file_size = None

    max_size = 50 * 1024 * 1024  # 50MB
    if file_size and file_size > max_size:
        await update.message.reply_text("📥 बड़ी फ़ाइल डाउनलोड करके भेज रहा हूँ...")
        local_file = "temp_video.mp4"
        with requests.get(direct, stream=True, timeout=60, headers={'User-Agent': 'Mozilla/5.0'}) as r:
            r.raise_for_status()
            with open(local_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        with open(local_file, 'rb') as video:
            await update.message.reply_video(video=video, caption="✅ असली वीडियो (yt-dlp)", supports_streaming=True)
        os.remove(local_file)
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=direct, caption="✅ असली वीडियो (yt-dlp)", supports_streaming=True)

# =================== वेबहुक सर्वर ===================
def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("BOT_TOKEN missing")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    if WEBHOOK_URL:
        print(f"🔗 Webhook set at: {WEBHOOK_URL}")
        app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)
    else:
        print("🤖 Polling mode (local)")
        app.run_polling()

if __name__ == "__main__":
    main()
