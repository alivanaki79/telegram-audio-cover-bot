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

async def set_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما اجازه این کار را ندارید.")
        return
    if not update.message.photo:
        await update.message.reply_text("لطفاً یک عکس ارسال کنید.")
        return
    file = await update.message.photo[-1].get_file()
    await file.download_to_drive("cover.jpg")

    config = load_config()
    config["cover_path"] = "cover.jpg"
    save_config(config)
    await update.message.reply_text("کاور جدید با موفقیت ذخیره شد.")

from PIL import Image

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Audio received")
    if not update.message.audio:
        return

    file = await context.bot.get_file(update.message.audio.file_id)
    file_path = "input.mp3"
    await file.download_to_drive(file_path)

    # تبدیل به MP3 برای اطمینان از فرمت
    sound = AudioSegment.from_mp3(file_path)
    sound.export("edited.mp3", format="mp3")

    # بارگذاری فایل برای افزودن تگ‌ها
    audio = MP3("edited.mp3", ID3=ID3)
    try:
        audio.add_tags()
    except:
        pass

    config = load_config()
    artist_name = config.get("artist_name", "@Unknown")
    cover_path = config.get("cover_path", "cover.jpg")

    # ری‌سایز کاور به 600x600
    img = Image.open(cover_path).convert("RGB")
    img = img.resize((600, 600))
    resized_cover_path = "resized_cover.jpg"
    img.save(resized_cover_path, format="JPEG")

    # حذف کاورهای قبلی
    for tag in list(audio.tags.keys()):
        if tag.startswith("APIC"):
            del audio.tags[tag]

    # افزودن کاور جدید
    with open(resized_cover_path, "rb") as img_file:
        audio.tags.add(APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,  # Front Cover
            desc='Cover',
            data=img_file.read()
        ))

    # افزودن نام هنرمند
    audio["TPE1"] = TPE1(encoding=3, text=[artist_name])
    audio.save()

    # ارسال به کانال
    await context.bot.send_audio(
        chat_id=CHANNEL_USERNAME,
        audio=open("edited.mp3", "rb"),
        title=update.message.audio.title or "Track",
        performer=artist_name
    )

    os.remove("input.mp3")
    os.remove("edited.mp3")
    os.remove(resized_cover_path)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("setartist", set_artist))
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r'^/setcover'), set_cover))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.run_polling()

