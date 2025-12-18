import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, ForceReply
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # int or str, chat id куда падать фидбеку

ASK_FEEDBACK = 1

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}! Отправь /feedback чтобы оставить отзыв.",
    )


async def feedback_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Напиши сюда свой фидбек одним или несколькими сообщениями. \nКогда закончишь — отправь /done.",
        reply_markup=ForceReply(selective=True),
    )
    context.user_data["feedback_chunks"] = []
    return ASK_FEEDBACK


async def collect_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data.setdefault("feedback_chunks", []).append(text)
    await update.message.reply_text("Принято. Можешь дописать ещё или нажать /done.")
    return ASK_FEEDBACK


async def feedback_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get("feedback_chunks"):
        await update.message.reply_text("Ты ничего не написал. Напиши хоть что‑нибудь или /cancel.")
        return ASK_FEEDBACK

    feedback_text = "\n".join(context.user_data["feedback_chunks"])

    user = update.effective_user
    chat = update.effective_chat

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    admin_text = (
        f"<b>Новый фидбек</b>\n"
        f"Время: {timestamp}\n"
        f"Пользователь: {user.full_name} (@{user.username or 'нет юзера'})\n"
        f"User ID: <code>{user.id}</code>\n"
        f"Chat ID: <code>{chat.id}</code>\n\n"
        f"<b>Текст:</b>\n"
        f"<code>{feedback_text}</code>"
    )

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_CHAT_ID),
                text=admin_text,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Не удалось отправить фидбек админу: %s", e)

    await update.message.reply_text("Спасибо за фидбек!")
    context.user_data["feedback_chunks"] = []
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Окей, отменил.")
    context.user_data["feedback_chunks"] = []
    return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — инфо\n"
        "/feedback — оставить фидбек\n"
        "/cancel — отменить ввод фидбека",
    )


def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в окружении")

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_entry)],
        states={
            ASK_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_feedback),
                CommandHandler("done", feedback_done),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(conv_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
