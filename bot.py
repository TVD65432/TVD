import os
import requests
from telegram import Update, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup
# TeraBox के लिए ज़रूरी लाइब्रेरी
from terabox import TeraBox

tb = TeraBox()

# ====================== डायरेक्ट लिंक निकालने के फंक्शन ======================

def terabox_direct(link: str) -> str:
    """TeraBox शेयर लिंक से डायरेक्ट डाउनलोड लिंक निकालता है"""
    try:
        direct = tb.get_direct_link(link)
        return direct
    except Exception:
        return None

def diskwala_direct(link: str) -> str:
    """DiskWala शेयर लिंक से डायरेक्ट डाउनलोड लिंक निकालता है (वेबसाइट स्क्रैप करके)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(link, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # सबसे पहले <video> टैग देखें
        video = soup.find('video')
        if video and video.get('src'):
            return video['src']

        # <source> टैग
        source = soup.find('source')
        if source and source.get('src'):
            return source['src']

        # कोई डाउनलोड बटन
        btn = soup.find('a', class_='download') or soup.find('a', id='download')
        if btn and btn.get('href'):
            return btn['href']

        # meta og:video
        meta = soup.find('meta', property='og:video')
        if meta and meta.get('content'):
            return meta['content']

        return None
    except Exception:
        return None

def get_direct_link(url: str) -> str:
    """दिए गए URL की पहचान करके सही डायरेक्ट लिंक देता है"""
    if 'terabox.com' in url or 'teraboxapp.com' in url:
        return terabox_direct(url)
    elif 'diskwala.com' in url:
        return diskwala_direct(url)
    else:
        return None

# ====================== टेलीग्राम बॉट हैंडलर ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("नमस्ते! डिस्कवाला या टेराबॉक्स का वीडियो शेयर लिंक भेजें।")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    direct = get_direct_link(url)

    if not direct:
        await update.message.reply_text("❌ डायरेक्ट डाउनलोड लिंक नहीं निकल सका। कृपया लिंक जाँचें।")
        return

    # फ़ाइल साइज़ चेक करें (50MB से ज़्यादा हो तो सर्वर पर डाउनलोड करना पड़ेगा)
    try:
        head = requests.head(direct, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        file_size = int(head.headers.get('content-length', 0))
    except:
        file_size = None

    max_size = 50 * 1024 * 1024  # 50 MB

    if file_size and file_size > max_size:
        await update.message.reply_text("📥 वीडियो 50MB से बड़ी है, डाउनलोड कर रहा हूँ...")
        local_file = "temp_video.mp4"
        # स्ट्रीम करके फ़ाइल डाउनलोड करें
        with requests.get(direct, stream=True, timeout=30, headers={'User-Agent': 'Mozilla/5.0'}) as r:
            r.raise_for_status()
            with open(local_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        with open(local_file, 'rb') as video:
            await update.message.reply_video(video=video, caption="✅ ये लीजिए आपकी वीडियो")
        os.remove(local_file)  # डाउनलोड फ़ाइल हटाएँ
    else:
        # 50MB से छोटी है, टेलीग्राम सीधे URL से खींच लेगा
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=direct, caption="✅ ये लीजिए आपकी वीडियो")

def main():
    # टोकन एनवायरनमेंट वेरिएबल से लें (Render पर सेट करेंगे)
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("❌ BOT_TOKEN एनवायरनमेंट वेरिएबल सेट नहीं है।")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("🤖 Bot चल रहा है...")
    app.run_polling()

if __name__ == "__main__":
    main()