import json
import logging
from typing import Any

import phonenumbers
from email_validator import validate_email, EmailNotValidError
from telegram.error import TimedOut, NetworkError, TelegramError, BadRequest

from screens import render_main_menu, render_about, render_catalog
from keyboards import get_main_menu_keyboard, get_basic_keyboard, get_product_keyboard, get_cart_keyboard
from strapi_api import (
    get_product_by_id, parse_product, download_product_image,
    get_or_create_cart, get_cart_details, add_product_to_cart,
    remove_cart_product, get_or_create_user, link_user_to_cart,
    create_order, get_active_order, clear_cart
)

logger = logging.getLogger("bot.handlers")


def _validate_email_syntax(email):
    """Validates the syntax of an email address using email-validator.

    Args:
        email (str): A string representing the email address to validate.

    Returns:
        str | None: The normalized email string if the syntax is valid, or None otherwise.
    """
    try:
        email_info = validate_email(email, check_deliverability=False)
        return email_info.normalized
    except EmailNotValidError:
        return None


def _validate_and_format_phone(phone_number, default_region="RU"):
    """Validates and formats a raw phone number string into E.164 format.

    Args:
        phone_number (str): A string representing the raw phone number.
        default_region (str): A two-letter ISO country code. Defaults to 'RU'.

    Returns:
        str | None: The formatted phone number string in E.164 format (e.g., '+79991234567')
        if valid, or None if the number is invalid or cannot be parsed.
    """
    try:
        parsed_number = phonenumbers.parse(phone_number, default_region)

        if phonenumbers.is_valid_number(parsed_number):
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None


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
    """Handles the MENU state. Routes catalog, cart, about, and active order.

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

    data = query.data

    if data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=False)

    if data == "about":
        return await render_about(query=query)

    if data == "cart":
        return await _handle_cart(update=update, context=context)

    if data == "active_order":
        session = context.bot_data["http_session"]
        redis_db = context.bot_data["redis_db"]
        url = context.bot_data["strapi_url"]
        token = context.bot_data["strapi_token"]
        user_role = context.bot_data["strapi_user_role"]
        user_password = context.bot_data["strapi_user_password"]
        tg_id = update.effective_chat.id

        strapi_user_id = await get_or_create_user(
            session=session, db=redis_db, url=url, token=token,
            user_role=user_role, user_password=user_password, email=None, tg_id=tg_id
        )
        if not strapi_user_id:
            await query.answer("У вас еще нет истории заказов.", show_alert=True)
            return "MENU"

        active_order = await get_active_order(session=session, url=url, token=token, user_id=strapi_user_id)
        if not active_order:
            await query.answer("У вас нет активных заказов в обработке.", show_alert=True)
            return "MENU"

        products = active_order.get("order_items", [])
        text = (f"📦 *Ваш активный заказ*\n\n"
                f"*Номер:* {active_order.get('order_id', '')}\n"
                f"*Статус:* в обработке ⏳\n"
                f"*Телефон:* {active_order.get('phone_number', '')}\n\n"
                f"*Состав заказа:*\n")

        if products:
            total = 0
            for index, product in enumerate(products, 1):
                cost = product["price"] * product["quantity"]
                total += cost
                text += f"{index}. {product['title']} - {product['quantity']} кг х {product['price']} руб. = {cost} руб.\n"
            text += (f"\n*Итого к оплате:* {total} руб.\n\n"
                     f"ℹ Для уточнения деталей заказа можете связаться с менеджером по телефону: +7-999-123-45-67")
        else:
            text += ("Не удалось получить данные о заказе...\n\n"
                     "ℹ Для уточнения деталей заказа можете связаться с менеджером по телефону: +7-999-123-45-67")

        await query.edit_message_text(
            text=text,
            reply_markup=get_basic_keyboard(),
            parse_mode="Markdown"
        )
        return "ACTIVE_ORDER"

    return "MENU"


async def _handle_active_order(update, context):
    """Handles the ACTIVE_ORDER state. Navigates back to menu or catalog.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.message:
        await update.effective_message.reply_text(text="Пожалуйста, используйте кнопки управления выше 👆")
        return "ACTIVE_ORDER"

    query = update.callback_query
    if not query or not query.data:
        return "ACTIVE_ORDER"

    data = query.data

    if data == "menu":
        return await render_main_menu(query=query)

    if data == "catalog":
        return await render_catalog(update=update, context=context, query=query, send_new=False)

    return "ACTIVE_ORDER"


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

    data = query.data

    if data == "menu":
        return await render_main_menu(query=query)

    if data == "catalog":
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

    data: Any = query.data

    if isinstance(data, str):
        if data == "menu":
            return await render_main_menu(query=query)

        if data == "cart":
            return await _handle_cart(update=update, context=context)

        if data == "catalog":
            return await render_catalog(update=update, context=context, query=query, send_new=False)

    if isinstance(data, dict):
        action = data.get("action")

        if action == "change_page":
            context.user_data["catalog_page"] = data["page"]
            return await render_catalog(update=update, context=context, query=query, send_new=False)

        if action == "view_product":
            session = context.bot_data["http_session"]
            redis_db = context.bot_data["redis_db"]
            url = context.bot_data["strapi_url"]
            token = context.bot_data["strapi_token"]
            tg_id = update.effective_chat.id

            product_id = data["id"]
            product = await get_product_by_id(session=session, db=redis_db, url=url, token=token, product_id=product_id)

            if not product:
                await query.edit_message_text(
                    text="ℹ️ Данные о товаре временно отсутствуют.\n\nПожалуйста, загляните позже!",
                    reply_markup=get_product_keyboard(product_id="", quantity_in_cart=0)
                )
                return "PRODUCT"

            cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
            cart_items = await get_cart_details(session=session, url=url, token=token, cart_id=cart_id)

            quantity_in_cart = 0
            if cart_items:
                for item in cart_items:
                    if item.get("product", {}).get("documentId") == product_id:
                        quantity_in_cart = item.get("quantity", 0)
                        break
            reply_markup = get_product_keyboard(product_id=product_id, quantity_in_cart=quantity_in_cart)

            try:
                await query.delete_message()
            except (TelegramError, BadRequest):
                pass

            caption, full_image_url = parse_product(url=url, product=product)

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

            await context.bot.send_message(chat_id=update.effective_chat.id, text=caption, reply_markup=reply_markup)
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

    data: Any = query.data

    if isinstance(data, str):
        if data == "catalog":
            return await render_catalog(update=update, context=context, query=query, send_new=True)

    if isinstance(data, dict):
        action = data.get("action")

        if action == "add_to_cart":
            session = context.bot_data["http_session"]
            redis_db = context.bot_data["redis_db"]
            url = context.bot_data["strapi_url"]
            token = context.bot_data["strapi_token"]
            tg_id = update.effective_chat.id

            product_id = data["id"]

            cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)
            if not cart_id:
                await query.answer("⚠️ Не удалось найти вашу корзину. Повторите позже.", show_alert=True)
                return "PRODUCT"

            is_added = await add_product_to_cart(session=session, url=url, token=token, cart_id=cart_id, product_id=product_id)
            if is_added:
                cart_items = await get_cart_details(session=session, url=url, token=token, cart_id=cart_id)

                new_quantity = 0
                if cart_items:
                    for item in cart_items:
                        if item.get("product", {}).get("documentId") == product_id:
                            new_quantity = item.get("quantity", 0)
                            break
                new_markup = get_product_keyboard(product_id=product_id, quantity_in_cart=new_quantity)

                await query.edit_message_reply_markup(reply_markup=new_markup)
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

    data: Any = query.data

    session = context.bot_data["http_session"]
    redis_db = context.bot_data["redis_db"]
    url = context.bot_data["strapi_url"]
    token = context.bot_data["strapi_token"]
    user_role = context.bot_data["strapi_user_role"]
    user_password = context.bot_data["strapi_user_password"]
    tg_id = update.effective_chat.id

    if isinstance(data, dict):
        action = data.get("action")

        if action == "delete_from_cart":
            cart_product_id = data["id"]
            is_deleted = await remove_cart_product(session=session, url=url, token=token, cart_product_id=cart_product_id)

            if is_deleted:
                await query.answer("💥 Товар удален из корзины.")
            else:
                await query.answer("⚠️ Не удалось удалить товар. Попробуйте позже.")
                return "CART"

    if isinstance(data, str):
        if data == "menu":
            return await render_main_menu(query=query)

        if data == "catalog":
            return await render_catalog(update=update, context=context, query=query, send_new=False)

        if data == "order":
            strapi_user_id = await get_or_create_user(
                session=session, db=redis_db, url=url, token=token,
                user_role=user_role, user_password=user_password, email=None, tg_id=tg_id
            )
            if strapi_user_id:
                active_order = await get_active_order(session=session, url=url, token=token, user_id=strapi_user_id)
                if active_order:
                    await query.answer("⚠️ Вы не можете сделать новый заказ, пока предыдущий заказ находится в обработке.",
                                       show_alert=True)
                    return "CART"

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

    user_input = update.message.text.strip().lower()
    email = _validate_email_syntax(email=user_input)

    if not email:
        await update.message.reply_text(
            text="❌ Некорректный формат почты. Пожалуйста, попробуйте еще раз.\n\nПример: example@mail.ru",
        )
        return "WAITING_EMAIL"

    loading_message = await update.message.reply_text("⏳ Регистрируем ваш профиль...")

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
        context.user_data["user_email"] = email
        await loading_message.edit_text(
            text=f"📞 Почта зарегистрирована!\n\nТеперь введите ваш номер телефона для связи с менеджером.\nПример: +79991234567"
        )
        return "WAITING_PHONE"
    else:
        await loading_message.edit_text(text="⚠️ Не удалось привязать вашу корзину к профилю.\nПопробуйте оформить заказ позже.",
                                        reply_markup=get_main_menu_keyboard())
        return "MENU"


async def _handle_phone(update, context):
    """Handles the WAITING_PHONE state. Validates phone and registers an order in Strapi.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        str: The next FSM state identifier.
    """
    if update.callback_query:
        await update.callback_query.answer("Пожалуйста, введите ваш телефон текстом.", show_alert=True)
        return "WAITING_PHONE"

    user_input = update.message.text.strip()
    phone_number = _validate_and_format_phone(phone_number=user_input)

    if not phone_number:
        await update.message.reply_text(
            text="❌ Неверный формат телефона. Пожалуйста, введите корректный номер.\nПример: +79991234567",
        )
        return "WAITING_PHONE"

    loading_message = await update.message.reply_text("⏳ Оформляем заказ...")

    session = context.bot_data["http_session"]
    redis_db = context.bot_data["redis_db"]
    url = context.bot_data["strapi_url"]
    token = context.bot_data["strapi_token"]
    user_role = context.bot_data["strapi_user_role"]
    user_password = context.bot_data["strapi_user_password"]
    user_email = context.user_data.get("user_email")
    tg_id = update.effective_chat.id

    cart_id = await get_or_create_cart(session=session, db=redis_db, url=url, token=token, tg_id=tg_id)

    strapi_user_id = await get_or_create_user(
        session=session, db=redis_db, url=url, token=token,
        user_role=user_role, user_password=user_password, email=user_email, tg_id=tg_id
    )
    if not strapi_user_id or not cart_id:
        await loading_message.edit_text("⚠️ Не удалось получить данные профиля.\nПожалуйста, начните оформление заново с корзины.")
        return "CART"

    cart_products = await get_cart_details(session=session, url=url, token=token, cart_id=cart_id)
    if not cart_products:
        await loading_message.edit_text("⚠️ Нельзя оформить заказ с пустой корзиной.")

    order_created = await create_order(
        session=session, url=url, token=token, user_id=strapi_user_id,
        phone_number=phone_number, cart_products=cart_products
    )
    if order_created:
        await clear_cart(session=session, url=url, token=token, cart_products=cart_products)

        cart_cache_key = f"strapi:user:{tg_id}:cart-id"
        await redis_db.delete(cart_cache_key)

        context.user_data.pop("user_email", None)

        await loading_message.edit_text(
            text=f"🎉 Заказ успешно оформлен!\n\nМенеджер свяжется с вами в ближайшее время для подтверждения заказа.",
            reply_markup=get_main_menu_keyboard(),
        )
        return "MENU"
    else:
        await loading_message.edit_text("⚠️ Произошла ошибка на сервере при создании заказа. Попробуйте еще раз позже.")
        return "WAITING_PHONE"


async def handle_invalid_button(update, context):
    """Handles button clicks if the received callback data has been tampered with or deleted from cache.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.

    Returns:
        None: This coroutine does not return a value.
    """
    query = update.callback_query
    if not query:
        return

    try:
        await query.answer(
            text="🔄 Магазин обновился. Пожалуйста, перезапустите бота командой /start.",
            show_alert=True
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔄 Магазин обновился.\nПожалуйста, перезапустите бота командой /start."
        )
    except (TelegramError, BadRequest):
        pass


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

    user_reply = None
    if update.message and update.message.text:
        user_reply = update.message.text
    elif update.callback_query and update.callback_query.data is not None:
        user_reply = update.callback_query.data

    if user_reply is None:
        return

    redis_db = context.bot_data["redis_db"]
    user_key = f"tg-bot:user:{tg_id}:state"
    lock_key = f"tg-bot:user:{tg_id}:lock"

    is_locked = not await redis_db.set(lock_key, "locked", ex=3, nx=True)
    if is_locked and update.callback_query:
        try:
            await update.callback_query.answer("Секунду, обрабатываю предыдущий запрос... ⏳")
        except (TelegramError, BadRequest):
            pass
        return

    if isinstance(user_reply, str) and user_reply == "/start":
        user_state = "START"
    else:
        cached_state = await redis_db.get(user_key)
        user_state = cached_state if cached_state else "START"

    states_functions = {
        "START": _start,
        "MENU": _handle_main_menu,
        "ACTIVE_ORDER": _handle_active_order,
        "ABOUT": _handle_about,
        "CATALOG": _handle_catalog,
        "PRODUCT": _handle_product,
        "CART": _handle_cart,
        "WAITING_EMAIL": _handle_email,
        "WAITING_PHONE": _handle_phone
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
            except (TelegramError, BadRequest):
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
