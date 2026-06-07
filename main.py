import os
import time
import json
import logging
from functools import partial

import redis
from dotenv import load_dotenv
from telegram.error import TimedOut, NetworkError
from redis.exceptions import ConnectionError, TimeoutError
from requests.exceptions import ReadTimeout, RequestException
from telegram import Update
from telegram.ext import (
    CallbackContext,
    Updater,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler
)

from logging_config import init_app_logging

logger = logging.getLogger(__name__)


def get_database_connection(host: str, port: int, password: str) -> redis.Redis:
    """Returns a connection to the Redis database, or creates a new one if one doesn't already exist."""
    try:
        redis_db = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=0,
            decode_responses=True,
            protocol=3
        )
        return redis_db
    except (ConnectionError, TimeoutError) as network_error:
        logger.error(f"Redis Network Connection error occurred: {network_error}")
    except Exception as e:
        logger.critical(f"An unexpected error occurred while establishing a connection to Redis: {e}", exc_info=True)


def start(update: Update, context: CallbackContext) -> str:
    """Handler for the START state."""
    update.message.reply_text(text="Hello!")
    return "ECHO"


def echo(update: Update, context: CallbackContext) -> str:
    """Handler for the ECHO state."""
    users_reply = update.message.text
    update.message.reply_text(users_reply)
    return "ECHO"


def handle_user_reply(update: Update, context: CallbackContext, db: redis.Redis) -> None:
    """Runs whenever a bot receives a message and decides how to process it."""
    if update.effective_chat:
        chat_id = update.effective_chat.id
    else:
        return

    if update.message:
        user_reply = update.message.text
    elif update.callback_query:
        user_reply = update.callback_query.data
        update.callback_query.answer()
    else:
        return

    user_key = f"tg-bot:user:{chat_id}"

    if user_reply == "/start":
        user_state = "START"
    else:
        user_state = db.get(user_key) or "START"

    states_functions = {
        "START": start,
        "ECHO": echo
    }
    state_handler = states_functions.get(user_state, start)

    try:
        next_state = state_handler(update, context)
        db.set(user_key, next_state)
    except Exception:
        raise


def handle_tg_error(update: Update, context: CallbackContext) -> None:
    """Handles Telegram bot errors and logs them."""
    error = context.error

    if isinstance(error, (TimedOut, ReadTimeout)):
        logger.warning("TG Bot: Network timeout occurred. Retrying connection...")
        return

    if isinstance(error, (NetworkError, RequestException)):
        logger.warning(f"TG Bot: Network connection issue occurred: {error}. Reconnecting...")
        time.sleep(5)
        return

    if update:
        json_fix = lambda obj: list(obj) if isinstance(obj, set) else str(obj)
        event_data = getattr(update, "to_dict", lambda: None)() or str(update)
        event_context = json.dumps(event_data, indent=2, ensure_ascii=False, default=json_fix)
    else:
        event_context = "N/A"

    logger.error(
        f"TG Bot: An unexpected error occurred:\n"
        f"--- EVENT CONTEXT ---\n"
        f"{event_context}\n"
        f"--- TRACEBACK ---",
        exc_info=True
    )


def main():
    init_app_logging(folder_name="logs", log_file="tg_bot.log")

    logger.info("Starting the Telegram bot...")

    try:
        load_dotenv()
        redis_host = os.environ["REDIS_HOST"]
        redis_port = int(os.environ["REDIS_PORT"])
        redis_password = os.environ["REDIS_PASSWORD"]
        tg_bot_token = os.environ["TG_BOT_TOKEN"]

        redis_db = get_database_connection(host=redis_host, port=redis_port, password=redis_password)

        updater = Updater(token=tg_bot_token)
        dispatcher = updater.dispatcher

        user_reply_handler = partial(handle_user_reply, db=redis_db)

        dispatcher.add_handler(CommandHandler("start", user_reply_handler))
        dispatcher.add_handler(CallbackQueryHandler(user_reply_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), user_reply_handler))
        dispatcher.add_error_handler(handle_tg_error)

        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.critical(f"The bot crashed during startup: {e}", exc_info=True)


if __name__ == "__main__":
    main()
