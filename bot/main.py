import os
import re
import json
import logging
from functools import partial

from dotenv import load_dotenv
from telegram.error import TimedOut, NetworkError, TelegramError
from telegram.ext import Updater, Filters, CallbackQueryHandler, CommandHandler, MessageHandler

from logging_config import init_app_logging
from database import get_database_connection
from strapi_api import StrapiClient
from screens import render_main_menu, render_about, render_catalog
from keyboards import get_main_menu_keyboard, get_product_keyboard, get_cart_keyboard

logger = logging.getLogger(__name__)


def start(update, context) -> str:
    """Handler for the START state."""
    update.effective_message.reply_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


def handle_main_menu(update, context, strapi_client) -> str:
    """Handler for the MENU state."""
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "MENU"

    query = update.callback_query

    if query.data == "catalog":
        return render_catalog(update=update, context=context, query=query, strapi_client=strapi_client, send_new=False)

    if query.data == "cart":
        return handle_cart(update, context, strapi_client=strapi_client)

    if query.data == "about":
        return render_about(query=query)

    return "MENU"


def handle_about(update, context, strapi_client) -> str:
    """Handler for the ABOUT state."""
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "ABOUT"

    query = update.callback_query

    if query.data == "menu":
        return render_main_menu(query=query)

    if query.data == "catalog":
        return render_catalog(update=update, context=context, query=query, strapi_client=strapi_client, send_new=False)

    return "ABOUT"


def handle_catalog(update, context, db, strapi_client) -> str:
    """Handler for the CATALOG state."""
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "CATALOG"

    query = update.callback_query

    if query.data == "menu":
        return render_main_menu(query=query)

    if query.data == "cart":
        return handle_cart(update, context, strapi_client=strapi_client)

    if query.data.startswith("product_"):
        product_id = query.data.split("_")[1]
        product = strapi_client.get_product_by_id(product_id=product_id)

        if not product:
            query.edit_message_text(
                text="ℹ️ Данные о товаре временно отсутствуют.\n\nПожалуйста, загляните позже!",
                reply_markup=get_product_keyboard(product_id="")
            )
            return "PRODUCT"

        caption, full_image_url = strapi_client.parse_product_data(product_data=product)
        reply_markup = get_product_keyboard(product_id=product_id)

        try:
            query.message.delete()
        except TelegramError:
            pass

        file_id_cache_key = f"tg-bot:product:{product_id}:image-id"
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
                logger.warning(f"The cached file_id for product {product_id} is out of date or invalid: {e}")
                pass

        if full_image_url:
            with strapi_client.download_product_image(image_url=full_image_url) as photo_file:
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


def handle_product(update, context, strapi_client) -> str:
    """Handler for the PRODUCT state."""
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "PRODUCT"

    query = update.callback_query

    if query.data == "catalog":
        return render_catalog(update=update, context=context, query=query, strapi_client=strapi_client, send_new=True)

    if query.data.startswith("add_"):
        product_id = query.data.split("_")[1]
        user_id = update.effective_chat.id

        cart_id = strapi_client.get_or_create_cart(tg_id=user_id)
        strapi_client.add_product_to_cart(cart_id=cart_id, product_id=product_id)

        query.answer("🛒 Товар успешно добавлен в корзину!")
        return "PRODUCT"

    return "PRODUCT"


def handle_cart(update, context, strapi_client) -> str:
    """Handler for the CART state."""
    if update.message:
        update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "CART"

    query = update.callback_query
    user_id = update.effective_chat.id

    if query.data == "menu":
        return render_main_menu(query=query)

    if query.data == "catalog":
        return render_catalog(update=update, context=context, query=query, strapi_client=strapi_client, send_new=False)

    if query.data.startswith("del_"):
        cart_product_id = query.data.split("_")[1]
        is_deleted = strapi_client.remove_cart_product(cart_product_id=cart_product_id)

        if is_deleted:
            query.answer("💥 Товар удален из корзины.")
        else:
            query.answer("⚠️ Не удалось удалить товар. Попробуйте позже.")
            return "CART"

    if query.data == "order":
        cart_id = strapi_client.get_or_create_cart(tg_id=user_id)
        cart_products = strapi_client.get_cart_details(cart_id=cart_id)

        if not cart_products:
            query.answer("⚠️ Нельзя оформить заказ с пустой корзиной!", show_alert=True)
            return "CART"

        query.edit_message_text(
            text="📧 Пожалуйста, введите ваш адрес электронной почты для оформления заказа:\nПример: example@mail.ru"
        )
        return "WAITING_EMAIL"

    cart_id = strapi_client.get_or_create_cart(tg_id=user_id)
    cart_items = strapi_client.get_cart_details(cart_id=cart_id)

    if not cart_items:
        text = "🛒 Ваша корзина пуста.\n\nЗагляните в 🐟 Каталог, чтобы выбрать свежую рыбу!"
        reply_markup = get_cart_keyboard(cart_products=[])
    else:
        text = "🛒 Ваш заказ:\n\n"
        total_price = 0

        for index, item in enumerate(cart_items, 1):
            product = item.get("product", {})
            title = product.get("title", f"Товар №{index}")
            price = product.get("price", 0)
            quantity = item.get("quantity", 1)
            cost = price * quantity
            total_price += cost

            text += f"{index}. {title}\n    └ {quantity} кг х {price} руб. = {cost} руб.\n\n"

        text += f"Итого: {total_price} руб."
        reply_markup = get_cart_keyboard(cart_products=cart_items)

    query.edit_message_text(text=text, reply_markup=reply_markup)
    return "CART"


def handle_email(update, context, strapi_client) -> str:
    """Handler for the WAITING_EMAIL state."""
    if update.callback_query:
        update.callback_query.answer("Пожалуйста, введите вашу почту текстом 👆", show_alert=True)
        return "WAITING_EMAIL"

    email = update.message.text.strip().lower()
    tg_id = update.effective_chat.id

    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(email_regex, email):
        update.message.reply_text(
            text="❌ Некорректный формат почты. Пожалуйста, попробуйте еще раз:\n\nПример: example@mail.ru",
        )
        return "WAITING_EMAIL"

    loading_message = update.message.reply_text("⏳ Оформляем заказ...")

    cart_id = strapi_client.get_or_create_cart(tg_id=tg_id)
    if not cart_id:
        loading_message.edit_text("⚠️ Ошибка сервера. Пожалуйста, попробуйте ввести почту еще раз чуть позже.")
        return "MENU"

    strapi_user_id = strapi_client.get_or_create_user(email=email, tg_id=tg_id)
    if not strapi_user_id:
        loading_message.edit_text("⚠️ Не удалось привязать почту. Попробуйте ввести почту еще раз чуть позже.")
        return "WAITING_EMAIL"

    is_linked = strapi_client.link_user_to_cart(cart_id=cart_id, user_id=strapi_user_id)
    if is_linked:
        loading_message.edit_text(
            text=f"🎉 Заказ успешно оформлен!\n\nПользователь с почтой {email} успешно зарегистрирован и привязан к "
                 f"вашей корзине. Наш менеджер скоро свяжется с вами.",
            reply_markup=get_main_menu_keyboard(),
        )
        return "MENU"
    else:
        loading_message.edit_text("⚠️ Заказ создан, но не удалось связать его с вашим профилем. Мы разберемся с этим!")
        return "MENU"


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
    else:
        return

    user_key = f"tg-bot:user:{chat_id}:state"
    lock_key = f"tg-bot:user:{chat_id}:lock"

    is_locked = not db.set(lock_key, "locked", ex=3, nx=True)
    if is_locked and update.callback_query:
        update.callback_query.answer("Секунду, обрабатываю предыдущий запрос... ⏳")
        return

    if user_reply == "/start":
        user_state = "START"
    else:
        user_state = db.get(user_key) or "START"

    states_functions = {
        "START": start,
        "MENU": partial(handle_main_menu, strapi_client=strapi_client),
        "ABOUT": partial(handle_about, strapi_client=strapi_client),
        "CATALOG": partial(handle_catalog, db=db, strapi_client=strapi_client),
        "PRODUCT": partial(handle_product, strapi_client=strapi_client),
        "CART": partial(handle_cart, strapi_client=strapi_client),
        "WAITING_EMAIL": partial(handle_email, strapi_client=strapi_client),
    }
    state_handler = states_functions.get(user_state, start)

    try:
        next_state = state_handler(update, context)
        db.set(user_key, next_state)
    except Exception as e:
        logger.error(f"An error occurred while handling state {user_state}: {e}")
        raise
    finally:
        db.delete(lock_key)

    if update.callback_query:
        try:
            update.callback_query.answer()
        except TelegramError:
            pass


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
        strapi_user_role = int(os.environ["STRAPI_USER_ROLE"])
        strapi_user_password = os.environ["STRAPI_USER_PASSWORD"]

        redis_db = get_database_connection(host=redis_host, port=redis_port, password=redis_password)
        strapi_client = StrapiClient(
            db=redis_db,
            token=strapi_token,
            url=strapi_url,
            user_role=strapi_user_role,
            user_password=strapi_user_password
        )

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
