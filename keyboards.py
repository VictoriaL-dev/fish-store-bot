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


def get_about_keyboard() -> InlineKeyboardMarkup:
    """Generates navigation buttons for the About screen."""
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
            InlineKeyboardButton("🐟 Каталог", callback_data="catalog")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_catalog_keyboard(products: list) -> InlineKeyboardMarkup:
    """Generates a product list keyboard based on data from Strapi."""
    keyboard = []
    if products:
        for index, product in enumerate(products, 1):
            product_id = product.get("documentId")
            product_title = product.get("title", f"Товар №{index}")
            keyboard.append([InlineKeyboardButton(f"{product_title}", callback_data=f"product_{product_id}")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
        InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_product_keyboard(product_id: str) -> InlineKeyboardMarkup:
    """Generates buttons for a specific product card."""
    keyboard = []
    if product_id:
        keyboard.append([InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_{product_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад в каталог", callback_data="catalog")])
    return InlineKeyboardMarkup(keyboard)


def get_cart_keyboard(cart_products: list) -> InlineKeyboardMarkup:
    """Generates a dynamic cart keyboard with quick delete buttons for each product."""
    keyboard = []
    if cart_products:
        for index, product in enumerate(cart_products, 1):
            cart_product_id = product.get("documentId")
            product_title = product.get("product", {}).get("title", f"Товар №{index}")
            keyboard.append([InlineKeyboardButton(f"❌ Удалить {product_title}", callback_data=f"del_{cart_product_id}")])
        keyboard.append([InlineKeyboardButton("💳 Оформить заказ", callback_data="order")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
        InlineKeyboardButton("🐟 Каталог", callback_data="catalog")
    ])
    return InlineKeyboardMarkup(keyboard)
