from telegram.error import TelegramError

from keyboards import get_main_menu_keyboard, get_catalog_keyboard


def render_main_menu(query) -> str:
    """Edits message to show the main menu screen."""
    query.edit_message_text(
        text="👋 Добро пожаловать в наш Рыбный Магазин!\n\nВыберите опцию из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )
    return "MENU"


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
