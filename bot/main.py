import os
import json
import logging
from functools import partial

from dotenv import load_dotenv
from telegram.error import TimedOut, NetworkError
from telegram.ext import Updater, Filters, CallbackQueryHandler, CommandHandler, MessageHandler

from logging_config import init_app_logging
from database import get_database_connection
from strapi_api import StrapiClient
from keyboards import (
    get_main_menu_keyboard,
    get_catalog_keyboard,
    get_back_to_main_menu_keyboard,
    get_back_to_catalog_keyboard
)

logger = logging.getLogger(__name__)


def start(update, context) -> str:
    """Handler for the START state.

    Sends the main menu to the user and puts it into the MENU state.
    """
    update.effective_message.reply_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


def handle_main_menu(update, context, strapi_client) -> str:
    """Handler for the MENU state.

    Waits for a click on the main menu buttons and switches the user to the corresponding state.
    """
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки меню выше 👆")
        return "MENU"

    query = update.callback_query

    if query.data == "catalog":
        products = strapi_client.get_all_products()

        if products:
            text = "📋 Наш ассортимент.\n\nВыберите интересующий товар для просмотра деталей:"
            reply_markup = get_catalog_keyboard(products=products)
        else:
            text = "ℹ️ Каталог временно пуст.\n\nНаша команда уже обновляет ассортимент. Пожалуйста, загляните позже!"
            reply_markup = get_back_to_main_menu_keyboard()

        query.edit_message_text(
            text=text,
            reply_markup=reply_markup
        )
        return "CATALOG"

    if query.data == "cart":
        query.answer("Корзина пока в разработке! 😉", show_alert=True)
        return "MENU"

    if query.data == "about":
        query.answer("О нас пока в разработке! 😉", show_alert=True)
        return "MENU"

    return "MENU"


def handle_catalog(update, context, db, strapi_client) -> str:
    """Handler for the CATALOG state.

    Waits for a click on a specific product and switches the user to the corresponding state.
    """
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки меню выше 👆")
        return "CATALOG"

    query = update.callback_query

    if query.data == "back_to_menu":
        query.edit_message_text(
            text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
            reply_markup=get_main_menu_keyboard()
        )
        return "MENU"

    if query.data.startswith("product_"):
        product_id = query.data.split("_")[1]
        product = strapi_client.get_product_by_id(product_id=product_id)

        if not product:
            query.edit_message_text(
                text="ℹ️ Данные о товаре временно отсутствуют.\n\nПожалуйста, загляните позже!",
                reply_markup=get_back_to_catalog_keyboard()
            )
            return "PRODUCT"

        caption, full_image_url = strapi_client.parse_product_data(product_data=product)
        reply_markup = get_back_to_catalog_keyboard()

        query.message.delete()

        file_id_cache_key = f"tg-bot:cache:product:{product_id}:file-id"
        cached_file_id = db.get(file_id_cache_key)

        if cached_file_id:
            try:
                context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=cached_file_id,
                    caption=caption,
                    reply_markup=reply_markup
                )
                return "PRODUCT"
            except Exception as e:
                logger.warning(f"The cached file_id is out of date or invalid: {e}")
                pass

        if full_image_url:
            photo_file = strapi_client.download_product_image(image_url=full_image_url)

            if photo_file:
                try:
                    sent_message = context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo_file,
                        caption=caption,
                        reply_markup=reply_markup
                    )
                    tg_file_id = sent_message.photo[-1].file_id
                    db.set(file_id_cache_key, tg_file_id, ex=2592000)
                    return "PRODUCT"
                except Exception as e:
                    logger.exception(f"Failed to send message with downloaded photo: {e}")
                    pass

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=reply_markup
        )
        return "PRODUCT"

    return "CATALOG"


def handle_product_card(update, context, strapi_client) -> str:
    """Handler for the PRODUCT state.

    Waits for a button press to return from the product card to the catalog.
    """
    if update.message:
        update.effective_message.reply_text(text="Используйте кнопку под товаром, чтобы вернуться в каталог 👆")
        return "PRODUCT"

    query = update.callback_query

    if query.data == "back_to_catalog":
        products = strapi_client.get_all_products()
        query.message.delete()

        if products:
            text = "📋 Наш ассортимент.\n\nВыберите интересующий товар для просмотра деталей:"
            reply_markup = get_catalog_keyboard(products=products)
        else:
            text = "ℹ️ Каталог временно пуст.\n\nНаша команда уже обновляет ассортимент. Пожалуйста, загляните позже!"
            reply_markup = get_back_to_main_menu_keyboard()

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
        return "CATALOG"

    return "PRODUCT"


def handle_user_reply(update, context, db, strapi_client) -> None:
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
        "MENU": partial(handle_main_menu, strapi_client=strapi_client),
        "CATALOG": partial(handle_catalog, db=db, strapi_client=strapi_client),
        "PRODUCT": partial(handle_product_card, strapi_client=strapi_client),
    }
    state_handler = states_functions.get(user_state, start)

    try:
        next_state = state_handler(update, context)
        db.set(user_key, next_state)
    except Exception:
        raise


def handle_tg_error(update, context) -> None:
    """Handles Telegram bot errors and logs them."""
    error = context.error

    if isinstance(error, TimedOut):
        logger.warning("TG Bot: Network timeout occurred with Telegram API.")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"TG Bot: Network connection issue occurred: {error}. Reconnecting...")
        return

    if update:
        json_fix = lambda obj: list(obj) if isinstance(obj, set) else str(obj)
        event_data = getattr(update, "to_dict", lambda: None)() or str(update)
        event_context = json.dumps(event_data, indent=2, ensure_ascii=False, default=json_fix)
    else:
        event_context = "N/A"

    logger.exception(
        f"TG Bot: An unexpected error occurred:\n"
        f"--- EVENT CONTEXT ---\n"
        f"{event_context}\n"
        f"--- TRACEBACK ---"
    )


def main():
    init_app_logging(folder_name="logs", log_file="tg_bot.log")

    logger.info("Launching the Telegram bot...")

    try:
        load_dotenv()
        redis_host = os.environ["REDIS_HOST"]
        redis_port = int(os.environ["REDIS_PORT"])
        redis_password = os.environ["REDIS_PASSWORD"]
        tg_bot_token = os.environ["TG_BOT_TOKEN"]
        strapi_token = os.environ["STRAPI_TOKEN"]
        strapi_url = os.environ["STRAPI_URL"]

        redis_db = get_database_connection(host=redis_host, port=redis_port, password=redis_password)
        strapi_client = StrapiClient(db=redis_db, strapi_token=strapi_token, strapi_url=strapi_url)

        updater = Updater(token=tg_bot_token)
        dispatcher = updater.dispatcher

        user_reply_handler = partial(handle_user_reply, db=redis_db, strapi_client=strapi_client)

        dispatcher.add_handler(CommandHandler("start", user_reply_handler))
        dispatcher.add_handler(CallbackQueryHandler(user_reply_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), user_reply_handler))
        dispatcher.add_error_handler(handle_tg_error)

        logger.info("The Telegram bot has been launched successfully.")

        updater.start_polling()
        updater.idle()

    except Exception as e:
        logger.exception(f"The Telegram bot crashed during launch: {e}")


if __name__ == "__main__":
    main()
