from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard():
    """Generates a standard main menu keyboard.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix containing buttons for 'Catalog',
            'Cart', and 'About us' sections.
    """
    keyboard = [
        [
            InlineKeyboardButton("🐟 Каталог", callback_data="catalog"),
            InlineKeyboardButton("🛒 Корзина", callback_data="cart")
        ],
        [InlineKeyboardButton("ℹ️ О нас / Контакты", callback_data="about")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_about_keyboard():
    """Generates navigation buttons for the About screen.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix with navigation shortcuts
            'Main menu' and 'Catalog'.
    """
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
            InlineKeyboardButton("🐟 Каталог", callback_data="catalog")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_catalog_keyboard(products):
    """Generates a product list keyboard based on data from Strapi.

    Args:
        products (list): A list of dictionaries representing products,
            retrieved from the Strapi API.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix with vertical product buttons
            and 'Main menu' and 'Cart' controls at the bottom.
    """
    keyboard = []
    if products:
        for index, product in enumerate(products, 1):
            product_id = product.get("documentId")
            product_title = product.get("title", f"Товар №{index}")
            if product_id:
                keyboard.append([InlineKeyboardButton(f"{product_title}", callback_data=f"product_{product_id}")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
        InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_product_keyboard(product_id):
    """Generates buttons for a specific product card.

    Args:
        product_id (str): The unique document identifier of the target product.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix containing an 'Add to cart' button
            and a 'Back to catalog' button.
    """
    keyboard = []
    if product_id:
        keyboard.append([InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_{product_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад в каталог", callback_data="catalog")])
    return InlineKeyboardMarkup(keyboard)


def get_cart_keyboard(cart_products):
    """Generates a dynamic cart keyboard with quick delete buttons for each product.

    Args:
        cart_products (list): A list of dictionaries representing cart items,
            including nested product structures from Strapi API.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix containing standard delete buttons for each
            item, an 'Order' button (if not empty), and 'Main menu' and 'Catalog' buttons.
    """
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
