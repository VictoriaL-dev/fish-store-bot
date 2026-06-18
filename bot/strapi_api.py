import json
import logging
from io import BytesIO
from contextlib import contextmanager

import redis
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class StrapiClient:

    def __init__(self, db: redis.Redis, url: str, token: str, user_role: int, user_password: str):
        """Initializes the Strapi client with support for Redis caching.

        Args:
            db (redis.Redis): The Redis database client instance used for caching.
            url (str): The base URL of the Strapi API.
            token (str): The authentication token for API requests.
            user_role (int): The numeric identifier of the user's role.
            user_password (str): The password of the user for authentication.
        """
        self.db = db
        self.url = url
        self.headers = {"Authorization": f"Bearer {token}"}
        self.user_role = user_role
        self.user_password = user_password

    def get_all_products(self) -> list:
        """Requests a list of all products from Strapi and caches them.

        Attempts to fetch the products from the Redis cache first. If not cached,
        sends a GET request to the Strapi API, stores the results in Redis with
        a 15-minute expiration time, and returns the data.

        Returns:
            list: A list of products. Returns an empty list if the request
                fails or an unexpected error occurs.
        """
        products_cache_key = "strapi:products"

        cached_products = self.db.get(products_cache_key)
        if cached_products:
            return json.loads(cached_products)

        endpoint = f"{self.url}/api/products"

        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            strapi_data = response.json()

            products = strapi_data.get("data", [])
            self.db.set(products_cache_key, json.dumps(products), ex=900)
            return products
        except RequestException as e:
            logger.error(f"An error occurred while requesting products: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting products: {e}")
        return []

    def get_product_by_id(self, product_id: str) -> dict:
        """Requests a single product from Strapi by its documentId along with its media data.

        Checks the Redis cache for the product data first. If not found, sends a
        GET request to the Strapi API with the `populate=*` query parameter to
        fetch the product and its relations. Stores the response in Redis with
        a 15-minute expiration time.

        Args:
            product_id (str): The unique document identifier of the product.

        Returns:
            dict: The product data dictionary including populated fields. Returns
                an empty dictionary if the request fails or an error occurs.
        """
        product_cache_key = f"strapi:product:{product_id}"

        cached_product = self.db.get(product_cache_key)
        if cached_product:
            return json.loads(cached_product)

        endpoint = f"{self.url}/api/products/{product_id}?populate=*"

        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            strapi_data = response.json()

            product_data = strapi_data.get("data", {})
            self.db.set(product_cache_key, json.dumps(product_data), ex=900)
            return product_data
        except RequestException as e:
            logger.error(f"An error occurred while requesting product_{product_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting product_{product_id}: {e}")
        return {}

    def parse_product_data(self, product_data: dict) -> tuple:
        """Parses JSON from Strapi and returns a tuple with the caption and full image url.

        Extracts the title, description, price, and media details from the provided
        product dictionary.

        Args:
            product_data (dict): A dictionary containing product attributes
                retrieved from Strapi.

        Returns:
            tuple: A tuple containing two elements:
                1) caption (str): Formatted string with product details.
                2) full_image_url (str or None): Complete URL to the image, or None if no picture data is found.
        """
        title = product_data.get("title", "Название отсутствует")
        description = product_data.get("description", "Описание отсутствует")
        price = product_data.get("price", 0)

        caption = (
            f"{title}\n\n"
            f"Цена: {price} руб. за кг\n\n"
            f"{description}\n\n"
        )

        picture_data = product_data.get("picture")
        if isinstance(picture_data, dict):
            image_url_relative = picture_data.get("url")
            full_image_url = f"{self.url}{image_url_relative}" if image_url_relative else None
        else:
            full_image_url = None
        return caption, full_image_url

    @contextmanager
    def download_product_image(self, image_url: str):
        """Downloads an image from Strapi and yields a BytesIO object ready for Telegram.

        Fetches the image data via a GET request, wraps it in a BytesIO stream,
        and automatically ensures the stream is closed after the context exits.

        Args:
            image_url (str): The absolute URL of the image to download.

        Returns:
            BytesIO or None:
                The downloaded image stream, or None if the operation fails.
        """
        if not image_url:
            yield None
            return

        photo_file = None

        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            photo_file = BytesIO(response.content)
            photo_file.name = "fish.jpg"
            yield photo_file
        except RequestException as e:
            logger.error(f"Failed to download image from URL {image_url}: {e}")
            yield None
        except Exception as e:
            logger.exception(f"An unexpected error occurred while downloading image from URL {image_url}: {e}")
            yield None
        finally:
            if photo_file:
                photo_file.close()

    def get_or_create_cart(self, tg_id: int) -> str:
        """Gets existing cart documentId or creates a new one for the Telegram user.

        First, checks the Redis cache for the user's cart ID. If not found,
        queries Strapi using a filter by `tg_id`. If the cart exists in Strapi,
        it caches and returns the ID. If no cart exists, sends a POST request
        to Strapi to create a new cart, then caches and returns its new ID.

        Args:
            tg_id (int): The unique Telegram user identifier.

        Returns:
            str: The cart document ID, or an empty string if operation fails.
        """
        cart_cache_key = f"strapi:user:{tg_id}:cart-id"

        cached_cart_id = self.db.get(cart_cache_key)
        if cached_cart_id:
            return cached_cart_id

        endpoint = f"{self.url}/api/carts"
        params = {"filters[tg_id][$eq]": str(tg_id)}

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            carts = response.json().get("data", [])
            cart_id = carts[0].get("documentId")

            if cart_id:
                self.db.set(cart_cache_key, cart_id, ex=86400)
                return cart_id
        except (RequestException, Exception):
            pass

        payload = {"data": {"tg_id": str(tg_id)}}

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            cart_data = response.json().get("data", {})
            cart_id = cart_data.get("documentId")

            if cart_id:
                self.db.set(cart_cache_key, cart_id, ex=86400)
                return cart_id
        except RequestException as e:
            logger.error(f"An error occurred while creating user's cart for tg_id {tg_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while creating user's cart for tg_id {tg_id}: {e}")
        return ""

    def get_cart_details(self, cart_id: str) -> list:
        """Fetches all items in the cart by its documentId with pre-populated product data.

        Args:
            cart_id (str): The unique document identifier of the cart.

        Returns:
            list: A list of cart products with nested product info, or an empty list if fails.
        """
        endpoint = f"{self.url}/api/cart-products"
        params = {
            "filters[cart][documentId][$eq]": cart_id,
            "populate[product][populate]": "*"
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            cart_products = response.json().get("data", [])
            return cart_products
        except RequestException as e:
            logger.error(f"An error occurred while requesting user's cart products for cart {cart_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting user's cart products for cart {cart_id}: {e}")
        return []

    def add_product_to_cart(self, cart_id: str, product_id: str) -> None:
        """Adds a product to the cart or increments its quantity if it already exists.

        Args:
            cart_id (str): The unique document identifier of the cart.
            product_id (str): The unique document identifier of the product.
        """
        endpoint = f"{self.url}/api/cart-products"
        params = {
            "filters[cart][documentId][$eq]": cart_id,
            "filters[product][documentId][$eq]": product_id
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            cart_product = response.json().get("data", [])
        except RequestException as e:
            logger.error(f"Failed to check existing cart products for cart {cart_id}: {e}")
            return
        except Exception as e:
            logger.exception(f"An unexpected error occurred while checking existing cart products for cart {cart_id}: {e}")
            return

        if cart_product:
            cart_product_id = cart_product[0].get("documentId")
            current_quantity = cart_product[0].get("quantity", 1)

            update_endpoint = f"{self.url}/api/cart-products/{cart_product_id}"
            payload = {"data": {"quantity": current_quantity + 1}}

            try:
                requests.put(update_endpoint, headers=self.headers, json=payload, timeout=10).raise_for_status()
            except RequestException as e:
                logger.error(f"Failed to update product quantity for cart product {cart_product_id}: {e}")
            except Exception as e:
                logger.exception(f"An unexpected error occurred while trying to update product quantity {cart_product_id}: {e}")
        else:
            payload = {
                "data": {
                    "quantity": 1,
                    "cart": cart_id,
                    "product": product_id
                }
            }

            try:
                requests.post(endpoint, headers=self.headers, json=payload, timeout=10).raise_for_status()
            except RequestException as e:
                logger.error(f"Failed to create new cart product {product_id} for cart {cart_id}: {e}")
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred while trying to add new product {product_id} to cart {cart_id}: {e}"
                )

    def remove_cart_product(self, cart_product_id: str) -> bool:
        """Deletes a specific cart product by its documentId.

        Args:
            cart_product_id (str): The unique document identifier of the cart product.

        Returns:
            bool: True if the product was successfully deleted, False otherwise.
        """
        endpoint = f"{self.url}/api/cart-products/{cart_product_id}"

        try:
            requests.delete(endpoint, headers=self.headers, timeout=10).raise_for_status()
            return True
        except RequestException as e:
            logger.error(f"Failed to delete cart product {cart_product_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while trying to delete cart product {cart_product_id}: {e}")
        return False

    def get_or_create_user(self, email: str, tg_id: int) -> str:
        """Finds a user by email or creates a new one.

        Args:
            email (str): The email address of the user.
            tg_id (int): The unique Telegram user identifier.

        Returns:
            str: The user document identifier, or an empty string if the operation fails.
        """
        user_cache_key = f"strapi:user:{email}:user-id"

        cached_user_id = self.db.get(user_cache_key)
        if cached_user_id:
            return cached_user_id

        endpoint = f"{self.url}/api/users"
        params = {
            "filters[email][$eq]": email
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            users = response.json()
            user_id = users[0].get("documentId")

            if user_id:
                self.db.set(user_cache_key, user_id, ex=86400)
                return user_id
        except (RequestException, Exception):
            pass

        payload = {
            "username": f"tg_{tg_id}",
            "email": email,
            "password": self.user_password,
            "confirmed": True,
            "role": self.user_role
        }

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            user_data = response.json()
            user_id = user_data.get("documentId")

            if user_id:
                self.db.set(user_cache_key, user_id, ex=86400)
                return user_id
        except RequestException as e:
            logger.error(f"Failed to create new user with email {email}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while creating new user with email {email}: {e}")
        return ""

    def link_user_to_cart(self, cart_id: str, user_id: str) -> bool:
        """Links the Strapi user to the specific cart.

        Args:
            cart_id (str): The unique document identifier of the cart.
            user_id (str): The unique document identifier of the user.

        Returns:
            bool: True if the user was successfully linked to the cart, False otherwise.
        """
        endpoint = f"{self.url}/api/carts/{cart_id}"
        payload = {
            "data": {
                "users_permissions_users": [user_id]
            }
        }

        try:
            requests.put(endpoint, headers=self.headers, json=payload, timeout=10).raise_for_status()
            return True
        except RequestException as e:
            logger.error(f"Failed to link user {user_id} to cart {cart_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while trying to link user {user_id} to cart {cart_id}: {e}")
        return False
