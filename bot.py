import os, re, json, requests
from telegram import Update, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup

# ======================= TERABOX डायरेक्ट लिंक =======================
def terabox_direct(share_url):
    """Terabox शेयर लिंक से सीधा MP4 लिंक निकाले (API + स्क्रैपिंग)"""
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
    }
    try:
        # 1. shorturl निकालें
        shorturl = share_url.rstrip('/').split('/s/')[-1].split('?')[0]
        # 2. Terabox की शॉर्टयूआरएल इन्फो API का उपयोग करें
        api = f'https://www.terabox.com/api/shorturlinfo?shorturl={shorturl}&app_id=250528&web=1&channel=0&clienttype=0'
        resp = session.get(api, headers=headers, timeout=20)
        data = resp.json()
        if data.get('errno') == 0 and data.get('list'):
            dlink = data['list'][0].get('dlink')
            if dlink:
                return dlink
    except:
        pass

    # 3. फ़ॉलबैक: पेज से jsData या og:video खोजें
    try:
        resp2 = session.get(share_url, headers=headers, timeout=20)
        # jsData JSON
        match = re.search(r'jsData\s*=\s*(\{.*?\});', resp2.text, re.DOTALL)
        if match:
            js = json.loads(match.group(1))
            dlink = js.get('dlink')
            if dlink:
                return dlink
        # og:video
        soup = BeautifulSoup(resp2.text, 'html.parser')
        meta = soup.find('meta', property='og:video')
        if meta and meta.get('content'):
            return meta['content']
        # <video> टैग
        video = soup.find('video')
        if video and video.get('src'):
            return video['src']
    except:
        pass
    return None

# ======================= DISKWALA डायरेक्ट लिंक =======================
def diskwala_direct(link):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(link, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # प्राथमिकता: <video> का src
        video = soup.find('video')
        if video and video.get('src'):
            return video['src']
        # <source> टैग
        source = soup.find('source')
        if source and source.get('src'):
            return source['src']
        # डाउनलोड बटन
        btn = soup.find('a', class_='download') or soup.find('a', id='download')
        if btn and btn.get('href'):
            return btn['href']
        # og:video मेटा
        meta = soup.find('meta', property='og:video')
        if meta and meta.get('content'):
            return meta['content']
        return None
    except:
        return None

# ======================= सामान्य लिंक पहचान =======================
def get_direct_link(url):
    if 'terabox.com' in url or 'teraboxapp.com' in url:
        return terabox_direct(url)
    elif 'diskwala.com' in url:
        return diskwala_direct(url)
    return None

# ======================= टेलीग्राम बॉट =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "नमस्ते! कृपया Terabox या DiskWala का पूरा शेयर लिंक भेजें।\n"
        "बॉट असली वीडियो निकाल कर डाउनलोड का विकल्प देगा।"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    direct = get_direct_link(url)
    if not direct:
        await update.message.reply_text("❌ डायरेक्ट वीडियो लिंक नहीं निकल सका। कृपया लिंक जाँचें।")
        return

    # फ़ाइल साइज़ चेक करें
    try:
        head = requests.head(direct, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        file_size = int(head.headers.get('content-length', 0))
    except:
        file_size = None

    max_direct_size = 50 * 1024 * 1024  # 50 MB

    if file_size and file_size > max_direct_size:
        await update.message.reply_text("📥 बड़ी फ़ाइल (50MB से अधिक) डाउनलोड करके भेज रहा हूँ...")
        local_file = "temp_video.mp4"
        with requests.get(direct, stream=True, timeout=60, headers={'User-Agent': 'Mozilla/5.0'}) as r:
            r.raise_for_status()
            with open(local_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        with open(local_file, 'rb') as video:
            await update.message.reply_video(video=video, caption="✅ आपकी वीडियो (असली, बड़ी फ़ाइल)", supports_streaming=True)
        os.remove(local_file)
    else:
        # छोटी फ़ाइल सीधे URL से भेजें
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=direct, caption="✅ आपकी वीडियो (असली)", supports_streaming=True)

# ======================= वेबहुक सर्वर =======================
def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable missing!")
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
