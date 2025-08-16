import logging
import os  # <-- Import the os module
from telegram import Update
from telegram.ext import Application, ChatJoinRequestHandler, CommandHandler, ContextTypes

# Set up basic logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get the bot token from an environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("FATAL: The TELEGRAM_BOT_TOKEN environment variable is not set.")
    exit(1) # Exit if the token is not found


async def approve_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    join_request = update.chat_join_request
    chat_id = join_request.chat.id
    user_id = join_request.from_user.id
    user_name = join_request.from_user.first_name

    logger.info(f"Received join request from {user_name} ({user_id}) for chat {chat_id}.")

    try:
        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        logger.info(f"Approved join request for {user_name} ({user_id}).")
    except Exception as e:
        logger.error(f"Failed to approve join request for {user_name} ({user_id}): {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! I am online and ready to approve new join requests.")


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(ChatJoinRequestHandler(callback=approve_chat_join_request))

    logger.info("Bot is starting...")
    application.run_polling()
    logger.info("Bot has stopped.")


if __name__ == "__main__":
    main()
