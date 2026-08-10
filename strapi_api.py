import json
import logging
from io import BytesIO
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import ClientError

logger = logging.getLogger("bot.strapi")


async def get_all_products(session, db, url, token):
    """Requests a list of all products from Strapi and caches them.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        db (redis.asyncio.Redis): The Redis client to use for storing cached products.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.

    Returns:
        list: A list of products. Returns an empty list if the request
            fails or an unexpected error occurs.
    """
    products_cache_key = "strapi:products"

    cached_products = await db.get(products_cache_key)
    if cached_products:
        return json.loads(cached_products)

    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/products"

    try:
        async with session.get(endpoint, headers=headers, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            products = response_json.get("data", [])

            if products:
                await db.set(products_cache_key, json.dumps(products), ex=900)
                return products
    except ClientError as e:
        logger.error(f"Failed to request products: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while requesting products: {e}")
    return []


async def get_product_by_id(session, db, url, token, product_id):
    """Requests a single product from Strapi by its documentId along with its media data.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        db (redis.asyncio.Redis): The Redis client to use for storing cached product.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        product_id (str): The unique document identifier of the product.

    Returns:
        dict: The product data dictionary including populated fields. Returns
            an empty dictionary if the request fails or an error occurs.
    """
    product_cache_key = f"strapi:product:{product_id}"

    cached_product = await db.get(product_cache_key)
    if cached_product:
        return json.loads(cached_product)

    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/products/{product_id}"
    params = {"populate": "*"}

    try:
        async with session.get(endpoint, headers=headers, params=params, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            product = response_json.get("data", {})

            if product:
                await db.set(product_cache_key, json.dumps(product), ex=900)
                return product
    except ClientError as e:
        logger.error(f"Failed to request product: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while requesting product: {e}")
    return {}


def parse_product(url, product):
    """Parses JSON from Strapi and returns a tuple with the caption and full image url.

    Args:
        url (str): The Strapi API endpoint URL.
        product (dict): A dictionary containing product attributes retrieved from Strapi.

    Returns:
        tuple [str, str | None]: A two-element tuple containing:
            - caption (str): Formatted string with product details.
            - full_image_url (str or None): Complete URL to the image, or None if no picture data is found.
    """
    title = product.get("title", "Название отсутствует")
    description = product.get("description", "Описание отсутствует")
    price = product.get("price", 0)

    caption = (
        f"{title}\n\n"
        f"Цена: {price} руб. за кг\n\n"
        f"{description}\n\n"
    )

    picture = product.get("picture")
    if isinstance(picture, dict):
        relative_image_url = picture.get("url")
        full_image_url = f"{url}{relative_image_url}" if relative_image_url else None
    else:
        full_image_url = None
    return caption, full_image_url


@asynccontextmanager
async def download_product_image(session, image_url):
    """Downloads an image from Strapi and yields a BytesIO object ready for Telegram.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        image_url (str): The absolute URL of the image to download.

    Yields:
        BytesIO or None: The downloaded image stream, or None if the operation fails.
    """
    if not image_url:
        yield None
        return

    photo_file = None

    try:
        async with session.get(image_url, timeout=5) as response:
            response.raise_for_status()
            content = await response.read()
            photo_file = BytesIO(content)
            photo_file.name = "product.jpg"
            yield photo_file
    except ClientError as e:
        logger.error(f"Failed to download image: {e}")
        yield None
    except Exception as e:
        logger.exception(f"Unexpected error while downloading image: {e}")
        yield None
    finally:
        if photo_file:
            photo_file.close()


async def get_or_create_cart(session, db, url, token, tg_id):
    """Gets existing cart documentId or creates a new one for the Telegram user.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        db (redis.asyncio.Redis): The Redis client to use for storing cached cart document identifier.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        tg_id (int): The unique Telegram user identifier.

    Returns:
        str | None: The cart document identifier, or None if operation fails.
    """
    cart_cache_key = f"strapi:user:{tg_id}:cart-id"

    cached_cart_id = await db.get(cart_cache_key)
    if cached_cart_id:
        return cached_cart_id

    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/carts"
    params = {"filters[tg_id][$eq]": str(tg_id)}

    try:
        async with session.get(endpoint, headers=headers, params=params, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            carts = response_json.get("data", [])

            if carts:
                cart_id = carts[0].get("documentId")
                if cart_id:
                    await db.set(cart_cache_key, cart_id, ex=86400)
                    return cart_id
    except (ClientError, Exception):
        pass

    payload = {"data": {"tg_id": str(tg_id)}}

    try:
        async with session.post(endpoint, headers=headers, json=payload, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            cart = response_json.get("data", {})
            cart_id = cart.get("documentId")

            if cart_id:
                await db.set(cart_cache_key, cart_id, ex=86400)
                return cart_id
    except ClientError as e:
        logger.error(f"Failed to create user's cart for tg id '{tg_id}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while creating user's cart for tg id '{tg_id}': {e}")
    return None


async def get_cart_details(session, url, token, cart_id):
    """Fetches all items in the cart by its documentId with pre-populated product data.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        cart_id (str): The unique document identifier of the cart.

    Returns:
        list: A list of cart products with nested product info, or an empty list if fails.
    """
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/cart-products"
    params = {
        "filters[cart][documentId][$eq]": cart_id,
        "populate[product][populate]": "*"
    }

    try:
        async with session.get(endpoint, headers=headers, params=params, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            cart_products = response_json.get("data", [])
            return cart_products
    except ClientError as e:
        logger.error(f"Failed to request user's cart products: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while requesting user's cart products: {e}")
    return []


async def add_product_to_cart(session, url, token, cart_id, product_id):
    """Adds a product to the cart or increments its quantity if it already exists.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        cart_id (str): The unique document identifier of the cart.
        product_id (str): The unique document identifier of the product.

    Returns:
        bool: True if the product was successfully added to the cart, otherwise False.
    """
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/cart-products"
    params = {
        "filters[cart][documentId][$eq]": cart_id,
        "filters[product][documentId][$eq]": product_id
    }

    try:
        async with session.get(endpoint, headers=headers, params=params, timeout=5) as response:
            response.raise_for_status()
            response_json = await response.json()
            cart_products = response_json.get("data", [])

        if cart_products:
            cart_product_id = cart_products[0].get("documentId")
            current_quantity = cart_products[0].get("quantity", 1)

            update_endpoint = f"{url}/api/cart-products/{cart_product_id}"
            payload = {"data": {"quantity": current_quantity + 1}}

            async with session.put(update_endpoint, headers=headers, json=payload, timeout=5) as response:
                response.raise_for_status()
                return True
        else:
            payload = {
                "data": {
                    "quantity": 1,
                    "cart": cart_id,
                    "product": product_id
                }
            }
            async with session.post(endpoint, headers=headers, json=payload, timeout=5) as response:
                response.raise_for_status()
                return True
    except ClientError as e:
        logger.error(f"Failed to manage cart product for cart '{cart_id}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while managing cart product for cart '{cart_id}': {e}")
    return False


async def remove_cart_product(session, url, token, cart_product_id):
    """Deletes a specific cart product by its documentId.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        cart_product_id (str): The unique document identifier of the cart product.

    Returns:
        bool: True if the product was successfully deleted, False otherwise.
    """
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/cart-products/{cart_product_id}"

    try:
        async with session.delete(endpoint, headers=headers, timeout=5) as response:
            response.raise_for_status()
            return True
    except ClientError as e:
        logger.error(f"Failed to delete cart product '{cart_product_id}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while trying to delete cart product '{cart_product_id}': {e}")
    return False


async def get_or_create_user(session, db, url, token, user_role, user_password,
                             email, tg_id):
    """Finds a user by username or creates a new one.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        db (redis.asyncio.Redis): The Redis client to use for storing cached user document identifier.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        user_role (int): The Strapi Authenticated user role ID.
        user_password (str): The password for automatic user creation.
        email (str | None): The email address of the user.
        tg_id (int): The unique Telegram user identifier.

    Returns:
        str | None: The user document identifier, or None if the operation fails.
    """
    user_cache_key = f"strapi:user:{tg_id}:user-id"

    cached_user_id = await db.get(user_cache_key)
    if cached_user_id:
        return cached_user_id

    username = f"tg_{tg_id}"
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/users"
    params = {"filters[username][$eq]": username}

    try:
        async with session.get(endpoint, headers=headers, params=params, timeout=5) as response:
            response.raise_for_status()
            users = await response.json()

            if users:
                user_id = users[0].get("documentId")
                if user_id:
                    await db.set(user_cache_key, user_id, ex=86400)
                    return user_id
    except (ClientError, Exception):
        pass

    payload = {
        "username": username,
        "email": email,
        "password": user_password,
        "confirmed": True,
        "role": user_role
    }

    try:
        async with session.post(endpoint, headers=headers, json=payload, timeout=5) as response:
            response.raise_for_status()
            user = await response.json()
            user_id = user.get("documentId")

            if user_id:
                await db.set(user_cache_key, user_id, ex=86400)
                return user_id
    except ClientError as e:
        logger.error(f"Failed to create new user for tg id '{tg_id}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while creating new user for tg id '{tg_id}': {e}")
    return None


async def link_user_to_cart(session, url, token, cart_id, user_id):
    """Links the Strapi user to the specific cart.

    Args:
        session (aiohttp.ClientSession): The active asynchronous HTTP session.
        url (str): The Strapi API endpoint URL.
        token (str): The Strapi API token to use.
        cart_id (str): The unique document identifier of the cart.
        user_id (str): The unique document identifier of the user.

    Returns:
        bool: True if the user was successfully linked to the cart, False otherwise.
    """
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"{url}/api/carts/{cart_id}"
    payload = {
        "data": {
            "user": user_id
        }
    }

    try:
        async with session.put(endpoint, headers=headers, json=payload, timeout=5) as response:
            response.raise_for_status()
            return True
    except ClientError as e:
        logger.error(f"Failed to link user '{user_id}' to cart '{cart_id}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while trying to link user '{user_id}' to cart '{cart_id}': {e}")
    return False
