from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates a standard main menu."""
    keyboard = [
        [
            InlineKeyboardButton("🐟 Каталог", callback_data="catalog"),
            InlineKeyboardButton("🛒 Корзина", callback_data="cart")
        ],
        [InlineKeyboardButton("ℹ️ О нас / Контакты", callback_data="about")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_catalog_keyboard(products: list) -> InlineKeyboardMarkup:
    """Generates a product list keyboard based on data from Strapi."""
    keyboard = []
    for product in products:
        product_id = product.get("documentId")
        product_name = product.get("title", "Название отсутствует.")
        keyboard.append([InlineKeyboardButton(f"{product_name}", callback_data=f"product_{product_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates a return button to the menu."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_to_menu")]])


def get_back_to_catalog_keyboard() -> InlineKeyboardMarkup:
    """Generates a return button from the product card to the catalog."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в каталог", callback_data="back_to_catalog")]])
