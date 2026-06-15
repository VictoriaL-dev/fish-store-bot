import json
import logging
from io import BytesIO

import redis
import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError, RequestException

logger = logging.getLogger(__name__)


class StrapiClient:

    def __init__(self, db: redis.Redis, strapi_url: str, strapi_token: str):
        """Initializes the Strapi client with support for Redis caching."""
        self.db = db
        self.strapi_url = strapi_url
        self.headers = {"Authorization": f"Bearer {strapi_token}"}

    def get_all_products(self) -> list:
        """Requests a list of all products from the Strapi API and caches them."""
        endpoint = f"{self.strapi_url}/api/products"
        products_cache_key = "tg-bot:cache:products"

        cached_products = self.db.get(products_cache_key)
        if cached_products:
            return json.loads(cached_products)

        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            strapi_data = response.json()

            products = strapi_data.get("data", [])
            self.db.set(products_cache_key, json.dumps(products), ex=900)
            return products

        except Timeout:
            logger.warning(f"Timeout occurred while requesting products via Strapi URL: {endpoint}")
            return []

        except ConnectionError:
            logger.error(f"Connection error occurred while connecting to Strapi URL: {endpoint}")
            return []

        except HTTPError as http_error:
            logger.error(
                f"Strapi returned HTTP error status {http_error.response.status_code} for URL: {endpoint}"
            )
            return []

        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting products from Strapi: {e}")
            return []

    def get_product_by_id(self, product_id: str) -> dict:
        """Requests a single product from Strapi by its ID along with its media data."""
        endpoint = f"{self.strapi_url}/api/products/{product_id}?populate=*"
        product_cache_key = f"tg-bot:cache:product:{product_id}"

        cached_product = self.db.get(product_cache_key)
        if cached_product:
            return json.loads(cached_product)

        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            strapi_data = response.json()

            product_data = strapi_data.get("data", {})
            self.db.set(product_cache_key, json.dumps(product_data), ex=900)
            return product_data

        except Timeout:
            logger.warning(f"Timeout occurred while requesting product_{product_id} via Strapi URL: {endpoint}")
            return {}

        except ConnectionError:
            logger.error(f"Connection error occurred while connecting to Strapi URL: {endpoint}")
            return {}

        except HTTPError as http_error:
            logger.error(
                f"Strapi returned HTTP error status {http_error.response.status_code} for URL: {endpoint}"
            )
            return {}

        except Exception as e:
            logger.exception(f"An unexpected error occurred while requesting product_{product_id} from Strapi: {e}")
            return {}

    def parse_product_data(self, product_data: dict) -> tuple:
        """Parses JSON from Strapi and returns a tuple with the caption and full image url."""
        title = product_data.get("title", "Название отсутствует.")
        description = product_data.get("description", "Описание отсутствует.")
        price = product_data.get("price", 0)

        caption = (
            f"{title}\n\n"
            f"Цена: {price} руб. за кг\n\n"
            f"{description}\n\n"
        )

        try:
            image_url_relative = product_data["picture"]["url"]
            full_image_url = f"{self.strapi_url}{image_url_relative}"
        except Exception:
            full_image_url = None
        return caption, full_image_url

    def download_product_image(self, image_url: str) -> BytesIO | None:
        """Downloads an image from Strapi and returns a BytesIO object ready for Telegram."""
        if not image_url:
            return None

        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            photo_file = BytesIO(response.content)
            photo_file.name = "fish.jpg"
            return photo_file

        except RequestException as e:
            logger.exception(f"Failed to download image from URL {image_url}: {e}")
            return None
