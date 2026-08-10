import logging

import aiohttp
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters
)

from config import settings
from handlers import handle_user_reply, handle_tg_error
from logging_config import init_app_logging, stop_app_logging
from database import get_db_connection, close_db_connection

logger = logging.getLogger("bot")


async def on_app_start(app):
    """Initializes the shared asynchronous aiohttp ClientSession and Redis database.

    Args:
        app (telegram.ext.Application): The building application instance.

    Returns:
        None: This coroutine does not return a value.
    """
    app.bot_data["http_session"] = aiohttp.ClientSession()

    redis_host = app.bot_data["redis_host"]
    redis_port = app.bot_data["redis_port"]
    redis_password = app.bot_data["redis_password"]

    redis_db = await get_db_connection(host=redis_host, port=redis_port, password=redis_password)
    app.bot_data["redis_db"] = redis_db

    logger.info("The Telegram bot has been launched successfully.")


async def on_app_stop(app):
    """Closes external database connections and an http session on application shutdown.

    Args:
        app (telegram.ext.Application): The shutting down application instance.

    Returns:
        None: This coroutine does not return a value.
    """
    logger.info("Shutting down the Telegram bot...")

    session = app.bot_data.get("http_session")
    if session and not session.closed:
        await session.close()

    redis_db = app.bot_data.get("redis_db")
    if redis_db:
        await close_db_connection(redis_db=redis_db)

    logger.info("The Telegram bot was successfully shut down.")


def main():
    """Initializes configuration, boots up background log queues, and runs the execution loop."""
    log_listener = init_app_logging(
        project_root=settings.project_root,
        folder_name="logs",
        log_file_name="tg_bot.log",
        log_level=settings.LOG_LEVEL
    )
    logger.info("Launching the Telegram bot...")

    try:
        app = (
            ApplicationBuilder()
            .token(settings.TG_BOT_TOKEN)
            .post_init(on_app_start)
            .post_stop(on_app_stop)
            .build()
        )

        app.bot_data["redis_host"] = settings.REDIS_HOST
        app.bot_data["redis_port"] = settings.REDIS_PORT
        app.bot_data["redis_password"] = settings.REDIS_PASSWORD
        app.bot_data["strapi_url"] = settings.STRAPI_URL
        app.bot_data["strapi_token"] = settings.STRAPI_TOKEN
        app.bot_data["strapi_user_role"] = settings.STRAPI_USER_ROLE
        app.bot_data["strapi_user_password"] = settings.STRAPI_USER_PASSWORD

        app.add_handler(CommandHandler("start", handle_user_reply))
        app.add_handler(CallbackQueryHandler(handle_user_reply))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_reply))

        app.add_error_handler(handle_tg_error)

        app.run_polling()
    except Exception as e:
        logger.exception(f"The Telegram bot crashed during launch: {e}")
    finally:
        stop_app_logging(listener=log_listener)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
