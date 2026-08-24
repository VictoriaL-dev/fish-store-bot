from telegram.error import TelegramError, BadRequest

from strapi_api import get_all_products
from keyboards import get_main_menu_keyboard, get_basic_keyboard, get_catalog_keyboard


async def render_main_menu(query):
    """Edits the current message to display the main menu screen.

    Args:
        query (telegram.CallbackQuery): The callback query that triggered
            this screen update.

    Returns:
        str: The next FSM state identifier 'MENU'.
    """
    await query.edit_message_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


async def render_about(query):
    """Edits the current message to display the 'About us' and contacts screen.

    Args:
        query (telegram.CallbackQuery): The callback query that triggered
            this screen update.

    Returns:
        str: The next FSM state identifier 'ABOUT'.
    """
    text = (
        "🐟 *Рыбный Магазин «Свежий Улов»*\n\n"
        "Мы поставляем самую свежую рыбу и морепродукты напрямую с Камчатки и Мурманска. "
        "Каждая позиция проходит строгий контроль качества перед тем, как попасть к вам на стол.\n\n"
        "📍 *Наш адрес:* г. Москва, ул. Рыбная, д. 10\n"
        "📞 *Контакты:* +7 (999) 123-45-67\n"
        "⏰ *Режим работы:* Ежедневно с 09:00 до 21:00\n\n"
        "Выберите интересующий раздел ниже, чтобы продолжить:"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=get_basic_keyboard(),
        parse_mode="Markdown"
    )
    return "ABOUT"


async def render_catalog(update, context, query, send_new, per_page=8):
    """Edits or sends a new message to show the paginated product catalog screen.

    Args:
        update (telegram.Update): The current Telegram update object.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The current callback context.
        query (telegram.CallbackQuery): The callback query that triggered this screen.
        send_new (bool): If True, deletes the old message and sends a new one;
            otherwise, edits the existing message text.
        per_page (int): Maximum items to display on a single page. Defaults to 8.

    Returns:
        str: The next FSM state identifier 'CATALOG'.
    """
    redis_db = context.bot_data["redis_db"]
    url = context.bot_data["strapi_url"]
    token = context.bot_data["strapi_token"]
    session = context.bot_data["http_session"]
    page = context.user_data.get("catalog_page", 1)

    products = await get_all_products(session=session, db=redis_db, url=url, token=token)

    if products:
        text = "📋 Наш ассортимент.\n\nВыберите интересующий товар для просмотра деталей:"
        reply_markup = get_catalog_keyboard(products=products, page=page, per_page=per_page)
    else:
        text = "ℹ️ Каталог временно пуст.\n\nНаша команда уже обновляет ассортимент. Пожалуйста, загляните позже!"
        reply_markup = get_catalog_keyboard(products=[], page=page, per_page=per_page)

    if send_new:
        try:
            await query.delete_message()
        except (TelegramError, BadRequest):
            pass

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    return "CATALOG"
