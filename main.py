import os, json
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def is_admin(user_id):
    config = load_config()
    return user_id in config.get("admin_ids", [])

async def set_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما اجازه این کار را ندارید.")
        return
    if not context.args:
        await update.message.reply_text("لطفاً نام جدید را وارد کنید.")
        return
    config = load_config()
    config["artist_name"] = " ".join(context.args)
    save_config(config)
    await update.message.reply_text(f"نام خواننده به {config['artist_name']} تغییر یافت.")

import requests

def send_audio_with_thumb(token, channel_username, audio_path, title, performer, thumb_path):
    url = f"https://api.telegram.org/bot{token}/sendAudio"

    with open(audio_path, 'rb') as audio_file, open(thumb_path, 'rb') as thumb_file:
        files = {
            'audio': audio_file,
            'thumb': thumb_file
        }
        data = {
            'chat_id': channel_username,
            'title': title,
            'performer': performer
        }
        response = requests.post(url, data=data, files=files)
        print("🔁 Response:", response.status_code, response.text)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Audio received")
    if not update.message.audio:
        return

    file = await context.bot.get_file(update.message.audio.file_id)
    file_path = "input.mp3"
    await file.download_to_drive(file_path)

    # تبدیل به فرمت مناسب
    sound = AudioSegment.from_mp3(file_path)
    sound.export("edited.mp3", format="mp3")

    audio = MP3("edited.mp3", ID3=ID3)
    try:
        audio.add_tags()
    except:
        pass

    # خواندن تنظیمات
    config = load_config()
    artist_name = config.get("artist_name", "@Unknown")
    cover_path = config.get("cover_path", "cover.jpg")

    # افزودن کاور و نام هنرمند
    with open(cover_path, "rb") as img:
        audio.tags.add(APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc=u'Cover',
            data=img.read()
        ))

    audio["TPE1"] = TPE1(encoding=3, text=[artist_name])
    audio.save()

    # ارسال فایل با thumbnail واقعی
    send_audio_with_thumb(
        BOT_TOKEN,
        CHANNEL_USERNAME,
        "edited.mp3",
        update.message.audio.title or "Track",
        artist_name,
        cover_path
    )

    os.remove("input.mp3")
    os.remove("edited.mp3")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("setartist", set_artist))
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r'^/setcover'), set_cover))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.run_polling()

