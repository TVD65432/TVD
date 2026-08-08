import os, re, json, requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup

# ======================= TERABOX डायरेक्ट लिंक (नया तरीका) =======================
def terabox_direct(share_url):
    """
    Terabox शेयर लिंक से सीधा वीडियो MP4 लिंक निकालता है।
    पहले API, फिर डाउनलोड पेज स्क्रैपिंग, फिर og:video आज़माता है।
    """
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
    }

    # --- तरीका 1: shorturlinfo API (पुराना, लेकिन कभी-कभी काम करता है) ---
    try:
        shorturl = share_url.rstrip('/').split('/s/')[-1].split('?')[0]
        api_url = f'https://www.terabox.com/api/shorturlinfo?shorturl={shorturl}&app_id=250528&web=1&channel=0&clienttype=0'
        resp = session.get(api_url, headers=headers, timeout=15)
        data = resp.json()
        if data.get('errno') == 0 and data.get('list'):
            dlink = data['list'][0].get('dlink')
            if dlink:
                return dlink
    except Exception:
        pass

    # --- तरीका 2: डाउनलोड पेज (sharing/link?surl=) से सीधा लिंक ---
    try:
        # sURL निकालें (अगर पहले से नहीं निकाला)
        if 'surl=' in share_url:
            surl = share_url.split('surl=')[-1].split('&')[0]
        elif '/s/' in share_url:
            surl = share_url.rstrip('/').split('/s/')[-1].split('?')[0]
        else:
            surl = shorturl  # ऊपर से मिला हुआ

        download_page = f'https://www.terabox.app/sharing/link?surl={surl}'
        resp2 = session.get(download_page, headers=headers, timeout=20)
        
        # पहले jsData JSON देखें
        match = re.search(r'window\.jsData\s*=\s*(\{.*?\});', resp2.text, re.DOTALL)
        if match:
            js = json.loads(match.group(1))
            dlink = js.get('dlink')
            if dlink:
                return dlink

        # फिर pageData (कुछ वर्ज़न में)
        match2 = re.search(r'window\.pageData\s*=\s*(\{.*?\});', resp2.text, re.DOTALL)
        if match2:
            page = json.loads(match2.group(1))
            dlink = page.get('dlink')
            if dlink:
                return dlink

        # <video> टैग से src
        soup = BeautifulSoup(resp2.text, 'html.parser')
        video_tag = soup.find('video')
        if video_tag and video_tag.get('src'):
            return video_tag['src']

        # og:video मेटा टैग
        meta = soup.find('meta', property='og:video')
        if meta and meta.get('content'):
            return meta['content']

    except Exception:
        pass

    # --- तरीका 3: सीधे शेयर URL से (पुराना स्क्रैपिंग) ---
    try:
        resp3 = session.get(share_url, headers=headers, timeout=20)
        # jsData
        match = re.search(r'jsData\s*=\s*(\{.*?\});', resp3.text, re.DOTALL)
        if match:
            js = json.loads(match.group(1))
            dlink = js.get('dlink')
            if dlink:
                return dlink
        # og:video
        soup = BeautifulSoup(resp3.text, 'html.parser')
        meta = soup.find('meta', property='og:video')
        if meta and meta.get('content'):
            return meta['content']
        video_tag = soup.find('video')
        if video_tag and video_tag.get('src'):
            return video_tag['src']
    except Exception:
        pass

    return None

# ======================= DISKWALA डायरेक्ट लिंक (अपडेटेड) =======================
def diskwala_direct(link):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'}
        resp = requests.get(link, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # प्राथमिकता क्रम में खोजें
        for tag in [
            soup.find('video'),
            soup.find('source'),
            soup.find('a', class_='download'),
            soup.find('a', id='download'),
            soup.find('meta', property='og:video')
        ]:
            if tag:
                src = tag.get('src') or tag.get('content') or tag.get('href')
                if src:
                    return src
        return None
    except Exception:
        return None

# ======================= सामान्य लिंक पहचान =======================
def get_direct_link(url):
    if 'terabox.com' in url or 'teraboxapp.com' in url or 'terabox.app' in url:
        return terabox_direct(url)
    elif 'diskwala.com' in url:
        return diskwala_direct(url)
    return None

# ======================= टेलीग्राम बॉट =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "नमस्ते! Terabox या DiskWala का शेयर लिंक भेजें।\n"
        "बॉट असली वीडियो निकालकर डाउनलोड का विकल्प देगा।"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    direct = get_direct_link(url)
    if not direct:
        await update.message.reply_text("❌ डायरेक्ट वीडियो लिंक नहीं निकल सका। कृपया सुनिश्चित करें:\n- लिंक सही और पूरा है\n- लिंक Terabox/DiskWala का है\n- फ़ाइल पब्लिक है")
        return

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
            await update.message.reply_video(video=video, caption="✅ असली वीडियो (बड़ी फ़ाइल)", supports_streaming=True)
        os.remove(local_file)
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=direct, caption="✅ असली वीडियो", supports_streaming=True)

# ======================= वेबहुक सर्वर =======================
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
