from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard():
    """Generates a standard main menu keyboard.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix containing buttons for 'Catalog',
            'Cart', 'About us', and 'My order' sections.
    """
    keyboard = [
        [
            InlineKeyboardButton("🐟 Каталог", callback_data="catalog"),
            InlineKeyboardButton("ℹ️ О нас / Контакты", callback_data="about")
        ],
        [
            InlineKeyboardButton("🛒 Корзина", callback_data="cart"),
            InlineKeyboardButton("📦 Мой заказ", callback_data="active_order")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_basic_keyboard():
    """Generates navigation buttons for the About us / My order screens.

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


def get_catalog_keyboard(products, page=1, per_page=8):
    """Generates a product list keyboard based on data from Strapi with pagination support.

    Args:
        products (list): A list of dictionaries representing products,
            retrieved from the Strapi API.
        page (int): Current 1-based page index. Defaults to 1.
        per_page (int): Maximum items to display on a single page. Defaults to 8.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix with vertical product buttons,
            dynamic page arrows, and 'Main menu' and 'Cart' controls at the bottom.
    """
    keyboard = []

    if products:
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        page_products = products[start_index:end_index]

        for index, product in enumerate(page_products, start_index + 1):
            product_id = product.get("documentId")
            product_title = product.get("title", f"Товар №{index}")
            if product_id:
                keyboard.append([InlineKeyboardButton(
                    f"{product_title}",
                    callback_data={"action": "view_product", "id": product_id}
                )])

        total_products = len(products)
        navigation_row = []

        if page > 1:
            navigation_row.append(InlineKeyboardButton(
                "⬅️ Назад",
                callback_data={"action": "change_page", "page": page - 1}
            ))
        if end_index < total_products:
            navigation_row.append(InlineKeyboardButton(
                "Вперед ➡️",
                callback_data={"action": "change_page", "page": page + 1}
            ))

        if navigation_row:
            keyboard.append(navigation_row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
        InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_product_keyboard(product_id, quantity_in_cart):
    """Generates buttons for a specific product card.

    Args:
        product_id (str): The unique document identifier of the target product.
        quantity_in_cart (int): Total weight/quantity of this specific item in user's cart.

    Returns:
        InlineKeyboardMarkup: A keyboard matrix containing an 'Add to cart' button
            and a 'Back to catalog' button.
    """
    keyboard = []
    if product_id:
        if quantity_in_cart > 0:
            button_text = f"🛒 Добавить 1 кг (в корзине: {quantity_in_cart} кг)"
        else:
            button_text = "🛒 Добавить в корзину (1 кг)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data={"action": "add_to_cart", "id": product_id})])
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
            keyboard.append([InlineKeyboardButton(
                f"❌ Удалить {product_title}",
                callback_data={"action": "delete_from_cart", "id": cart_product_id}
            )])
        keyboard.append([InlineKeyboardButton("💳 Оформить заказ", callback_data="order")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="menu"),
        InlineKeyboardButton("🐟 Каталог", callback_data="catalog")
    ])
    return InlineKeyboardMarkup(keyboard)
