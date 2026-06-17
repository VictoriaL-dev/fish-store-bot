import json
import logging
from io import BytesIO
from contextlib import contextmanager

import redis
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class StrapiClient:

    def __init__(self, db: redis.Redis, strapi_url: str, strapi_token: str):
        """Initializes the Strapi client with support for Redis caching."""
        self.db = db
        self.strapi_url = strapi_url
        self.headers = {"Authorization": f"Bearer {strapi_token}"}

    def get_all_products(self) -> list:
        """Requests a list of all products from the Strapi and caches them."""
        products_cache_key = "tg-bot:cache:products"
        cached_products = self.db.get(products_cache_key)
        if cached_products:
            return json.loads(cached_products)

        endpoint = f"{self.strapi_url}/api/products"
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
        """Requests a single product from Strapi by its documentId along with its media data."""
        product_cache_key = f"tg-bot:cache:product:{product_id}"
        cached_product = self.db.get(product_cache_key)
        if cached_product:
            return json.loads(cached_product)

        endpoint = f"{self.strapi_url}/api/products/{product_id}?populate=*"
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
        """Parses JSON from Strapi and returns a tuple with the caption and full image url."""
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
            full_image_url = f"{self.strapi_url}{image_url_relative}" if image_url_relative else None
        else:
            full_image_url = None
        return caption, full_image_url

    @contextmanager
    def download_product_image(self, image_url: str):
        """Downloads an image from Strapi and yields a BytesIO object ready for Telegram."""
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
        """Gets existing cart documentId or creates a new one for the TG user."""
        cart_cache_key = f"tg-bot:user:{tg_id}:cart-id"
        cached_cart_id = self.db.get(cart_cache_key)
        if cached_cart_id:
            return cached_cart_id

        endpoint = f"{self.strapi_url}/api/carts"
        params = {"filters[tg_id][$eq]": str(tg_id)}
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            carts = response.json().get("data", [])
            cart_id = carts[0].get("documentId")

            if cart_id:
                self.db.set(cart_cache_key, cart_id, ex=86400)
                return cart_id
        except RequestException, Exception:
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
        """Fetches all items in the cart by its documentId with pre-populated product data."""
        endpoint = f"{self.strapi_url}/api/cart-products"
        params = {
            "filters[cart][documentId][$eq]": cart_id,
            "populate[product][populate]": "*"
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            products = response.json().get("data", [])
            return products
        except RequestException as e:
            logger.error(f"An error occurred while requesting user's cart products: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting user's cart products: {e}")
        return []

    def add_product_to_cart(self, cart_id: str, product_id: str) -> None:
        """Adds a product to the cart or increments its quantity if it already exists."""
        endpoint = f"{self.strapi_url}/api/cart-products"
        params = {
            "filters[cart][documentId][$eq]": cart_id,
            "filters[product][documentId][$eq]": product_id
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            cart_products = response.json().get("data", [])
        except RequestException as e:
            logger.error(f"Failed to check existing cart products for cart {cart_id}: {e}")
            return
        except Exception as e:
            logger.exception(f"An unexpected error occurred while checking existing cart products for cart {cart_id}: {e}")
            return

        if cart_products:
            cart_product_id = cart_products[0].get("documentId")
            current_quantity = cart_products[0].get("quantity", 1)

            update_endpoint = f"{self.strapi_url}/api/cart-products/{cart_product_id}"
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
        """Deletes a specific cart product by its documentId."""
        endpoint = f"{self.strapi_url}/api/cart-products/{cart_product_id}"
        try:
            requests.delete(endpoint, headers=self.headers, timeout=10).raise_for_status()
            return True
        except RequestException as e:
            logger.error(f"Failed to delete cart product {cart_product_id}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while trying to delete cart product {cart_product_id}: {e}")
        return False
