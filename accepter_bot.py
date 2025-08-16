import logging
import os
from telegram import Update, error
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatJoinRequestHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import pymongo

# --- Configuration ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI") # New environment variable for our database

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Database Connection ---
try:
    client = pymongo.MongoClient(MONGODB_URI)
    db = client.bot_db # The database name can be anything
    channels_collection = db.channels # A collection is like a table
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.critical(f"Could not connect to MongoDB: {e}")
    client = None # Ensure client is None if connection fails

# --- Database Functions (MongoDB version) ---
def add_channel(chat_id: int):
    """Adds or updates a channel with a default welcome message."""
    default_message = "Welcome! Your request to join has been approved."
    channels_collection.update_one(
        {"_id": chat_id},
        {"$setOnInsert": {"welcome_message": default_message}},
        upsert=True
    )

def get_welcome_message(chat_id: int) -> str:
    """Gets the welcome message for a channel."""
    channel_data = channels_collection.find_one({"_id": chat_id})
    return channel_data.get("welcome_message") if channel_data else None

# --- Conversation Handler States ---
AWAIT_FORWARD = 0

# --- Bot Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hello! I use MongoDB to manage channels.\nUse /connect to link me to your channel."
    )

async def connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the /connect conversation."""
    await update.message.reply_text(
        "Please forward any message from the channel you want me to manage.\n"
        "Make sure I am an admin with 'Invite Users' permission."
    )
    return AWAIT_FORWARD

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the forwarded message to get channel ID."""
    chat = update.message.forward_from_chat
    if not chat:
        await update.message.reply_text("This is not a forwarded message from a channel. Please try again.")
        return AWAIT_FORWARD

    chat_id = chat.id
    chat_title = chat.title

    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not (bot_member.status == "administrator" and bot_member.can_invite_users):
            await update.message.reply_text(f"I am not an admin in '{chat_title}' or I lack 'Invite Users' permission.")
            return ConversationHandler.END

        add_channel(chat_id)
        await update.message.reply_text(f"✅ Successfully connected to channel: {chat_title}.")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")
        logger.error(f"Error in handle_forwarded_message: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# --- Core Join Request Handler ---
async def approve_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    join_request = update.chat_join_request
    chat_id = join_request.chat.id
    user_id = join_request.from_user.id
    user_name = join_request.from_user.first_name

    welcome_message = get_welcome_message(chat_id)
    if not welcome_message:
        return # Ignore requests for channels not in our database

    try:
        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        logger.info(f"Approved join request for {user_name} in chat {chat_id}.")
        
        try:
            await context.bot.send_message(chat_id=user_id, text=welcome_message)
            logger.info(f"Sent welcome message to {user_name}.")
        except error.Forbidden:
            logger.warning(f"Could not send PM to {user_name} (blocked bot).")

    except Exception as e:
        logger.error(f"Failed to process join request for {user_name}: {e}")

# --- Main Bot Function ---
def main() -> None:
    if not all([BOT_TOKEN, MONGODB_URI, client]):
        logger.critical("Missing BOT_TOKEN or MONGODB_URI, or failed to connect to DB. Exiting.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("connect", connect_start)],
        states={AWAIT_FORWARD: [MessageHandler(filters.FORWARDED & filters.ChatType.CHANNEL, handle_forwarded_message)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(ChatJoinRequestHandler(callback=approve_chat_join_request))
    
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()