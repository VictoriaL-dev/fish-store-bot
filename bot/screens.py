from telegram.error import TelegramError

from keyboards import get_main_menu_keyboard, get_about_keyboard, get_catalog_keyboard


def render_main_menu(query) -> str:
    """Edits message to show the main menu screen."""
    query.edit_message_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


def render_about(query) -> str:
    """Edits message to show the About us screen."""
    text = (
        "🐟 *Рыбный Магазин «Свежий Улов»*\n\n"
        "Мы поставляем самую свежую рыбу и морепродукты напрямую с Камчатки и Мурманска. "
        "Каждая позиция проходит строгий контроль качества перед тем, как попасть к вам на стол.\n\n"
        "📍 *Наш адрес:* г. Москва, ул. Рыбная, д. 10\n"
        "📞 *Контакты:* +7 (999) 123-45-67\n"
        "⏰ *Режим работы:* Ежедневно с 09:00 до 21:00\n\n"
        "Выберите интересующий раздел ниже, чтобы продолжить:"
    )
    query.edit_message_text(
        text=text,
        reply_markup=get_about_keyboard(),
        parse_mode="Markdown"
    )
    return "ABOUT"


def render_catalog(update, context, query, strapi_client, send_new) -> str:
    """Edits or sends a new message to show the product catalog screen."""
    products = strapi_client.get_all_products()

    if products:
        text = "📋 Наш ассортимент.\n\nВыберите интересующий товар для просмотра деталей:"
        reply_markup = get_catalog_keyboard(products=products)
    else:
        text = "ℹ️ Каталог временно пуст.\n\nНаша команда уже обновляет ассортимент. Пожалуйста, загляните позже!"
        reply_markup = get_catalog_keyboard(products=[])

    if send_new:
        try:
            query.message.delete()
        except TelegramError:
            pass

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        query.edit_message_text(text=text, reply_markup=reply_markup)

    return "CATALOG"
