import re
import json
import logging

from telegram.error import TimedOut, NetworkError, TelegramError

from screens import render_main_menu, render_about, render_catalog
from keyboards import get_main_menu_keyboard, get_product_keyboard, get_cart_keyboard
from strapi_api import (
    get_product_by_id,
    parse_product,
    download_product_image,
    get_or_create_cart,
    get_cart_details,
    add_product_to_cart,
    remove_cart_product,
    get_or_create_user,
    link_user_to_cart
)

logger = logging.getLogger("bot.handlers")


async def _start(update, context):
    """Handles the START state. Sends the main greeting.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier 'MENU'.
    """
    await update.effective_message.reply_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


async def _handle_main_menu(update, context):
    """Handles the MENU state. Routes catalog, cart, and about actions.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier based on the user selection.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "MENU"

    query = update.callback_query

    if not query or not query.data:
        return "MENU"

    if query.data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=False)

    if query.data == "cart":
        return await _handle_cart(update=update, context=context)

    if query.data == "about":
        return await render_about(query=query)

    return "MENU"


async def _handle_about(update, context):
    """Handles the ABOUT state. Navigates back to menu or catalog.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "ABOUT"

    query = update.callback_query

    if not query or not query.data:
        return "ABOUT"

    if query.data == "menu":
        return await render_main_menu(query=query)

    if query.data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=False)

    return "ABOUT"


async def _handle_catalog(update, context):
    """Handles the CATALOG state. Fetches and displays a list of products.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "CATALOG"

    query = update.callback_query

    if not query or not query.data:
        return "CATALOG"

    if query.data == "menu":
        return await render_main_menu(query=query)

    if query.data == "cart":
        return await _handle_cart(update=update, context=context)

    if query.data.startswith("product_"):
        session = context.bot_data["http_session"]
        redis_db = context.bot_data["redis_db"]
        url = context.bot_data["strapi_url"]
        token = context.bot_data["strapi_token"]

        product_id = query.data.split("_")[1]
        product = await get_product_by_id(session=session, db=redis_db, url=url, token=token, product_id=product_id)

        if not product:
            await query.edit_message_text(
                text="ℹ️ Данные о товаре временно отсутствуют.\n\nПожалуйста, загляните позже!",
                reply_markup=get_product_keyboard(product_id="")
            )
            return "PRODUCT"

        caption, full_image_url = parse_product(url=url, product=product)
        reply_markup = get_product_keyboard(product_id=product_id)

        try:
            await query.delete_message()
        except TelegramError:
            pass

        file_id_cache_key = f"tg-bot:product:{product_id}:image-id"
        cached_file_id = await redis_db.get(file_id_cache_key)

        if cached_file_id:
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=cached_file_id,
                    caption=caption, reply_markup=reply_markup
                )
                return "PRODUCT"
            except Exception as e:
                logger.warning(f"The cached file id for product '{product_id}' is out of date or invalid: {e}")
                pass

        if full_image_url:
            async with download_product_image(session=session, image_url=full_image_url) as photo_file:
                if photo_file:
                    try:
                        sent_message = await context.bot.send_photo(
                            chat_id=update.effective_chat.id, photo=photo_file,
                            caption=caption, reply_markup=reply_markup
                        )
                        tg_file_id = sent_message.photo[-1].file_id
                        await redis_db.set(file_id_cache_key, tg_file_id, ex=2592000)
                        return "PRODUCT"
                    except Exception as e:
                        logger.exception(f"Failed to send message with downloaded photo: {e}")
                        pass

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=reply_markup
        )
        return "PRODUCT"

    return "CATALOG"


async def _handle_product(update, context):
    """Handles the PRODUCT state. Displays a specific product card and processes adding it to the cart.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier 'PRODUCT'.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "PRODUCT"

    query = update.callback_query

    if not query or not query.data:
        return "PRODUCT"

    if query.data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=True)

    if query.data.startswith("add_"):
        session = context.bot_data["http_session"]
        redis_db = context.bot_data["redis_db"]
        url = context.bot_data["strapi_url"]
        token = context.bot_data["strapi_token"]
        tg_id = update.effective_chat.id

        cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
        if not cart_id:
            await query.answer("⚠️ Не удалось найти вашу корзину. Повторите позже.", show_alert=True)
            return "PRODUCT"

        product_id = query.data.split("_")[1]
        is_added = await add_product_to_cart(session=session, url=url, token=token, cart_id=cart_id, product_id=product_id)
        if is_added:
            await query.answer("🛒 Товар успешно добавлен в корзину!")
        else:
            await query.answer("⚠ Не удалось добавить товар в корзину.")
        return "PRODUCT"

    return "PRODUCT"


async def _handle_cart(update, context):
    """Handles the CART state. Manages dynamic item list and order transition.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "CART"

    query = update.callback_query

    if not query or not query.data:
        return "CART"

    session = context.bot_data["http_session"]
    redis_db = context.bot_data["redis_db"]
    url = context.bot_data["strapi_url"]
    token = context.bot_data["strapi_token"]
    tg_id = update.effective_chat.id

    if query.data == "menu":
        return await render_main_menu(query=query)

    if query.data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=False)

    if query.data.startswith("del_"):
        cart_product_id = query.data.split("_")[1]
        is_deleted = await remove_cart_product(session=session, url=url, token=token, cart_product_id=cart_product_id)

        if is_deleted:
            await query.answer("💥 Товар удален из корзины.")
        else:
            await query.answer("⚠️ Не удалось удалить товар. Попробуйте позже.")
            return "CART"

    if query.data == "order":
        cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
        if not cart_id:
            await query.answer("⚠️ Не удалось найти вашу корзину. Повторите позже.", show_alert=True)
            return "CART"

        cart_products = await get_cart_details(session=session, url=url, token=token, cart_id=cart_id)
        if not cart_products:
            await query.answer("⚠️ Нельзя оформить заказ с пустой корзиной.", show_alert=True)
            return "CART"

        await query.edit_message_text(
            text="📧 Пожалуйста, введите ваш адрес электронной почты для оформления заказа.\nПример: example@mail.ru"
        )
        return "WAITING_EMAIL"

    cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
    if not cart_id:
        await query.answer("⚠️ Не удалось найти вашу корзину. Повторите позже.", show_alert=True)
        return "CART"

    cart_items = await get_cart_details(session=session, url=url, token=token, cart_id=cart_id)
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

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return "CART"


async def _handle_email(update, context):
    """Handles the WAITING_EMAIL state. Validates email and creates Strapi profile.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.callback_query:
        await update.callback_query.answer("Пожалуйста, введите вашу почту текстом.", show_alert=True)
        return "WAITING_EMAIL"

    email = update.message.text.strip().lower()
    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"

    if not re.match(email_regex, email):
        await update.message.reply_text(
            text="❌ Некорректный формат почты. Пожалуйста, попробуйте еще раз.\n\nПример: example@mail.ru",
        )
        return "WAITING_EMAIL"

    loading_message = await update.message.reply_text("⏳ Оформляем заказ...")

    redis_db = context.bot_data["redis_db"]
    session = context.bot_data["http_session"]
    url = context.bot_data["strapi_url"]
    token = context.bot_data["strapi_token"]
    user_role = context.bot_data["strapi_user_role"]
    user_password = context.bot_data["strapi_user_password"]
    tg_id = update.effective_chat.id

    cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
    if not cart_id:
        await loading_message.edit_text("⚠️ Не удалось найти вашу корзину. Попробуйте ввести почту позже.")
        return "WAITING_EMAIL"

    strapi_user_id = await get_or_create_user(
        session=session, db=redis_db, url=url, token=token,
        user_role=user_role, user_password=user_password, email=email, tg_id=tg_id
    )
    if not strapi_user_id:
        await loading_message.edit_text("⚠️ Не удалось зарегистрировать профиль. Попробуйте ввести почту позже.")
        return "WAITING_EMAIL"

    is_linked = await link_user_to_cart(session=session, url=url, token=token, cart_id=cart_id, user_id=strapi_user_id)
    if is_linked:
        await loading_message.edit_text(
            text=f"🎉 Заказ успешно оформлен!\n\nПользователь с почтой {email} успешно зарегистрирован и привязан к "
                 f"вашей корзине. Наш менеджер скоро свяжется с вами.",
            reply_markup=get_main_menu_keyboard()
        )
        return "MENU"
    else:
        await loading_message.edit_text("⚠️ Заказ создан, но не удалось связать его с вашим профилем. Мы разберемся с этим!")
        return "MENU"


async def handle_user_reply(update, context):
    """Manages custom FSM state routing.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        None: This coroutine does not return a value.
    """
    if not update.effective_chat:
        return
    tg_id = update.effective_chat.id

    if update.message and update.message.text:
        user_reply = update.message.text
    elif update.callback_query and update.callback_query.data:
        user_reply = update.callback_query.data
    else:
        return

    redis_db = context.bot_data["redis_db"]

    user_key = f"tg-bot:user:{tg_id}:state"
    lock_key = f"tg-bot:user:{tg_id}:lock"

    is_locked = not await redis_db.set(lock_key, "locked", ex=3, nx=True)
    if is_locked and update.callback_query:
        try:
            await update.callback_query.answer("Секунду, обрабатываю предыдущий запрос... ⏳")
        except TelegramError:
            pass
        return

    if user_reply == "/start":
        user_state = "START"
    else:
        cached_state = await redis_db.get(user_key)
        user_state = cached_state if cached_state else "START"

    states_functions = {
        "START": _start,
        "MENU": _handle_main_menu,
        "ABOUT": _handle_about,
        "CATALOG": _handle_catalog,
        "PRODUCT": _handle_product,
        "CART": _handle_cart,
        "WAITING_EMAIL": _handle_email
    }
    state_handler = states_functions.get(user_state, _start)

    try:
        next_state = await state_handler(update, context)
        if next_state:
            await redis_db.set(user_key, next_state, ex=86400)
    except Exception as e:
        logger.error(f"An error occurred while handling state {user_state}: {e}")
        raise
    finally:
        await redis_db.delete(lock_key)

        if update.callback_query:
            try:
                await update.callback_query.answer()
            except TelegramError:
                pass


async def handle_tg_error(update, context):
    """Catches unexpected Telegram bot exceptions and flushes events payload to non-blocking logs.

    Args:
        update (object): The Telegram raw update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        None: This coroutine does not return a value.
    """
    error = context.error

    if isinstance(error, TimedOut):
        logger.warning("TG Bot: Network timeout occurred with Telegram API.")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"TG Bot: Network connection issue occurred: {error}")
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
