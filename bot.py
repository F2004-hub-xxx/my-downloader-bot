import os
import yt_dlp
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.environ.get("BOT_TOKEN", "ضع_التوكن_هنا")

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

def get_info(url: str) -> dict:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    formats = []
    seen = set()
    for f in reversed(info.get("formats", [])):
        if f.get("vcodec") == "none" or f.get("acodec") == "none":
            continue
        height = f.get("height")
        if not height or height in seen:
            continue
        seen.add(height)
        size = f.get("filesize") or f.get("filesize_approx") or 0
        size_str = f"{size / 1_000_000:.1f} MB" if size else "حجم غير معروف"
        formats.append({
            "format_id": f["format_id"],
            "label": f"🎬 {height}p — {size_str}",
            "height": height,
        })
    formats.append({
        "format_id": "bestaudio/best",
        "label": "🎵 صوت فقط MP3",
        "height": 0
    })
    duration = info.get("duration", 0)
    mins = int(duration // 60)
    secs = int(duration % 60)
    duration_str = f"{mins}:{secs:02d}" if duration else "غير معروف"
    return {
        "title": info.get("title", "بدون عنوان"),
        "thumbnail": info.get("thumbnail"),
        "duration": duration_str,
        "formats": sorted(formats, key=lambda x: x["height"], reverse=True)[:6],
    }

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, fmt: str):
    msg = await update.effective_message.reply_text("⏳ جاري التحميل...")
    audio_only = fmt == "bestaudio/best"
    ydl_opts = {"outtmpl": "/tmp/%(title)s.%(ext)s", "quiet": True, "no_warnings": True}
    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })
    else:
        ydl_opts["format"] = f"{fmt}+bestaudio/best"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            filepath = ydl.prepare_filename(info)
            if audio_only:
                filepath = os.path.splitext(filepath)[0] + ".mp3"
        size = os.path.getsize(filepath)
        if size > 50 * 1_000_000:
            await msg.edit_text(f"⚠️ الفيديو كبير جداً ({size/1e6:.0f} MB)\nتليجرام مش بيقبل أكبر من 50 MB.\nجرب جودة أقل.")
        else:
            await msg.edit_text("✅ تم — جاري الإرسال...")
            with open(filepath, "rb") as f:
                if audio_only:
                    await update.effective_message.reply_audio(f, title=title)
                else:
                    await update.effective_message.reply_video(f, caption=f"🎬 {title}")
            await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ حصل خطأ:\n{e}")
    finally:
        try:
            for fn in os.listdir("/tmp"):
                if fn.endswith((".mp4", ".mkv", ".webm", ".mp3", ".m4a")):
                    os.remove(f"/tmp/{fn}")
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً! أنا بوت تحميل الفيديوهات 🎬\n\n"
        "ابعتلي أي لينك من:\n"
        "• يوتيوب\n• إنستجرام\n• تيك توك\n• فيسبوك\n• تويتر/X\n\n"
        "⬇️ ابعت اللينك دلوقتي"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not is_url(url):
        await update.message.reply_text("❌ ابعتلي لينك صحيح يبدأ بـ http أو https")
        return
    msg = await update.message.reply_text("🔍 بجيب معلومات الفيديو...")
    try:
        info = get_info(url)
        context.user_data["url"] = url
        buttons = [
            [InlineKeyboardButton(f["label"], callback_data=f["format_id"])]
            for f in info["formats"]
        ]
        caption = (
            f"🎬 *{info['title']}*\n"
            f"⏱ المدة: {info['duration']}\n\n"
            f"اختار الجودة:"
        )
        await msg.delete()
        if info["thumbnail"]:
            try:
                await update.message.reply_photo(
                    photo=info["thumbnail"],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except:
                await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await msg.edit_text(f"❌ مش قادر أجيب الفيديو:\n{e}")

async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data
    url = context.user_data.get("url")
    if not url:
        await query.message.reply_text("❌ ابعتلي اللينك تاني من فضلك")
        return
    await query.message.delete()
    await download_and_send(update, context, url, fmt)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_quality_choice))
    print("✅ البوت شغال!")
    app.run_polling()

if __name__ == "__main__":
    main()
