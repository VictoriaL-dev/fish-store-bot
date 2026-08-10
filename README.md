# 🐟 Telegram Fish Store Bot
An asynchronous Telegram bot tailored for a fish store. This application bridges a sleek 
and highly interactive Telegram customer interface with a powerful `Strapi CMS` backend for real-time 
inventory management, catalog distribution, and secure user processing. 

By leveraging an asynchronous `Redis` connection pool, the bot manages independent customer session 
states (FSM) and high-speed memory locks to guarantee a non-blocking user experience under request concurrency. 
The entire network architecture is built on cooperative multitasking via `asyncio`, utilizing `aiohttp` 
and `python-telegram-bot v22.x` to enable customers to seamlessly browse fresh product assortments, modify shopping carts, 
and finalize order details dynamically right from their devices without structural I/O bottlenecks.


## 📌 Table of Contents
- [⚙️ Tech Stack](#-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🛠️ Installation and Setup](#-installation-and-setup)
- [🚀 Quick Start Guide](#-quick-start-guide)
  - [Development Server Launch](#development-server-launch)
- [📊 Database Models Architecture](#-database-models-architecture-strapi-v5)
- [🔑 Strapi v5 Backend Configuration](#-strapi-v5-backend-configuration)
- [🔐 Managing PostgreSQL via Adminer](#-managing-postgresql-via-adminer-docker-only)
- [🔍 Inspecting Redis Data via Docker](#-inspecting-redis-data-via-docker)


## ⚙️ Tech Stack
- **Operating System:** Linux, macOS, or Windows (via WSL2)
- **Language:** `Python 3.11+`
- **Database**: `PostgreSQL` & `Redis` (via Docker)
- **Configuration:** `pydantic-settings` & `pydantic`
- **Backend:** `Node.js v24.x` & `Strapi`
- **Async Telegram Bot Framework:** `python-telegram-bot v22.x`
- **Async HTTP Framework:** `aiohttp`
- **Containerization & Orchestration:** `Docker` & `Docker Compose`


## 📁 Project Structure
```text
.
├── logs/                     # Dynamically generated application logs folder
├── strapi/                   # Strapi files
├── .env.example              # Example of environment variable configuration
├── config.py                 # Central application settings mapper
├── database.py               # Connection pool setup for Redis
├── logging_config.py         # Non-blocking async queue logger
├── keyboards.py              # Dynamic InlineKeyboardMarkup factories for navigation controls
├── screens.py                # Interface rendering functions layer for message transitions
├── handlers.py               # Core asynchronous FSM step handlers routing user navigation
├── strapi_api.py             # Asynchronous Strapi CMS HTTP integration engine
├── main.py                   # Main entry point for the Telegram bot
├── docker-compose-dev.yaml   # Docker services orchestration
└── requirements.txt          # Python dependencies
```


## 🛠️ Installation and Setup
### Prerequisites:
- [Node.js](https://nodejs.org/en) (v20, v22, or v24)
- [Python](https://www.python.org/) (v3.11 or higher)
- [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) (if you're on Windows and plan to use Docker Compose)
- Redis server (running [locally](https://redis-docs.ru/operate/oss_and_stack/install/install-redis/) or via [Docker Desktop](https://www.docker.com/products/docker-desktop/))
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Basic knowledge of [Strapi CMS](https://docs.strapi.io/cms/quick-start)
- Strapi API [token](https://docs.strapi.io/cms/features/api-tokens)

### Basic Setup:
#### 1. Clone the repository:
```bash
git clone https://github.com/...
cd project-directory
```

#### 2. Configure environment variables:
Create a `.env` file in the root directory based on `.env.example` and fill in the variables for `PostgreSQL` if you plan 
to run it through `Docker`, or leave them blank:
```dotenv
# PostgreSQL
DATABASE_PORT=5433
DATABASE_NAME=postgres_db
DATABASE_USERNAME=postgres_user
DATABASE_PASSWORD=your_postgres_password

# Adminer
ADMINER_PORT=8080

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Logging
LOG_LEVEL=INFO

# Strapi API
STRAPI_TOKEN=your_full_access_or_custom_token
STRAPI_URL=http://localhost:1337
STRAPI_USER_ROLE=1  # Authenticated user role id
STRAPI_USER_PASSWORD=your_password_for_strapi_user_creation

# Telegram
TG_BOT_TOKEN=your_bot_token
```

### Backend Setup (Strapi)
#### 1. Initialize a new Strapi project:
From the root directory, create a Strapi app inside the `strapi` folder:
```bash
cd project-directory
npx create-strapi-app@5.48.1 strapi
```

#### 2. Configure environment variables in `strapi/.env`:
In the automatically created `.env` file in the `strapi` folder configure your database choice.
Make sure the database variables in `strapi/.env` and the root `.env` match:
```dotenv
# Database
DATABASE_CLIENT=postgres
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5433
DATABASE_NAME=fish_store
DATABASE_USERNAME=fish_store_user
DATABASE_PASSWORD=your_postgres_password
```

### Frontend Setup (Telegram Bot)
#### 1. Set up a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate # on Windows
source venv/bin/activate # on Linux / macOS
```

#### 2. Install Python dependencies:
```bash
pip install -r requirements.txt
```


## 🚀 Quick Start Guide
### Development Server Launch
#### 1. Spin up PostgreSQL and Redis using Docker:
```bash
docker-compose -f docker-compose-dev.yaml up -d
```
> ℹ️ _Note: Wait a few seconds for the database healthcheck to pass before proceeding._

#### 2. Start the Strapi development server:
```bash
cd strapi
npm run develop
```
You can access the admin panel at [http://localhost:1337/admin](http://localhost:1337/admin).

#### 3. Run the Telegram bot:
Open a new terminal in the root directory, activate your Python virtual environment, and start the bot:
```bash
python main.py
```

#### 4. Test the bot: 
Open Telegram, find your bot, and send the `/start` command.


## 📊 Database Models Architecture (Strapi v5)
The database relies on a junction model (CartProduct) to handle a custom Many-to-Many relationship between Carts and Products, 
allowing the bot to store unique metadata like product quantities.

#### 1. User (System Model: users-permissions)
Extends the standard Strapi user model to associate customers with their active sessions.
- `username` (String) — Unique Telegram identifier.
- `email` (Email) — Customer's email.
- `password` (Password) — Auto-generated secure password.
- `cart` (Relation) — Cart has many Users linkage.
#### 2. Product
Stores the shop's assortment data.
- `title` (String) — Name of the fish / seafood item.
- `description` (Long Text) — Detailed product description.
- `price` (Number) — Price per 1 kilogram.
- `picture` (Media: Single Media) — Image file uploaded to the Media Library.
- `cart_products` (Relation) — Product belongs to many CartProducts.
#### 3. Cart
Maintains live Telegram user sessions.
- `tg_id` (String / BigInt) — Unique Telegram Chat ID.
- `users_permissions_users` (Relation) — Cart belongs to many Users.
- `cart_products` (Relation) — Cart belongs to many CartProducts.
#### 4. CartProduct (Junction Model)
Acts as a pivot table to keep track of dynamic quantities for items inside specific carts.
- `cart` (Relation) — Cart has many CartProducts.
- `product` (Relation) — Product has many CartProducts.
- `quantity` (Integer) — The weight of items added.


## 🔑 Strapi v5 Backend Configuration
To ensure the Telegram bot can successfully communicate with Strapi v5, you need to configure specific roles and 
permissions in your Strapi Admin Panel [http://localhost:1337/admin](http://localhost:1337/admin).

### How to Find the Authenticated Role ID
When the bot automatically registers a new customer using their email during checkout, it forces Strapi to assign them 
to a default system role (typically Authenticated). To find the exact ID of this role for your strapi_api configuration:
1. Navigate to Settings ➔ Roles (under the Users & Permissions Plugin section).
2. Click on the Authenticated role to open its settings.
3. Look at your browser's address bar. The URL will end with a specific number (e.g., `.../users-permissions/roles/1`).
4. This number is your Authenticated Role ID. Set this value in your `.env` file.

### Permissions Required for a Custom API Token or Full Access Token
If you are connecting your Telegram bot to Strapi using a Custom API Token (generated via Settings ➔ API Tokens with 
token type set to Custom), you must explicitly check the boxes for the following permissions at the bottom of the token 
settings page:

#### 📦 Core Store Models (Custom Content-Types)
`Cart`:
  - find (allows checking if a user already has a shopping cart)
  - create (allows creating a new shopping cart for a first-time user)
  - update (allows linking a Strapi User to an existing Cart during checkout)

`Cart-Product`:
  - find (allows reading cart items to display them in the telegram cart screen)
  - create (allows adding a new item to the cart)
  - update (allows incrementing or decrementing product quantities)
  - delete (allows removing an item from the cart)

`Product`:
  - find (allows pulling the full list of products for the catalog)
  - findOne (allows opening a detailed product description card)

#### 👥 System Models (Advanced Plugins):
`Users-Permissions` (under the User subsection)
  - find (allows looking up if a customer's email is already registered)
  - create (allows registering a new user profile with their email during checkout)

`Upload` (Media Library plugin):
  - find (allows the bot to deep-populate and extract relative URLs for fish images stored inside product relations)


## 🔐 Managing PostgreSQL via Adminer (Docker only)
This project includes `Adminer`, a lightweight and fast database management interface available via web browser. It 
is configured to run inside a `Docker` container alongside `PostgreSQL`.

### How to Access Adminer
#### 1. Make sure your Docker container is running:
```bash
docker-compose -f docker-compose-dev.yaml up -d
```
#### 2. Open your web browser and navigate to: [http://localhost:8080](http://localhost:8080).
#### 3. Fill in the login form using your environment variables from the `.env` file:
- **System:** `PostgreSQL`
- **Server:** `postgres` *(This must match the service name defined in your `docker-compose-dev.yaml` file)*
- **Username:** `[Your DATABASE_USERNAME]`
- **Password:** `[Your DATABASE_PASSWORD]`
- **Database:** `[Your DATABASE_NAME]`
#### 4. Click login. You can now view tables, run custom SQL queries, and manage data directly from your browser.


## 🔍 Inspecting Redis Data via Docker
#### 1. Access the Redis container CLI.
Run the following command to open the interactive Redis CLI inside your running container:
```bash
docker compose -f docker-compose-dev.yaml exec redis redis-cli
127.0.0.1:6379> AUTH <your_redis_password>
```

Or you can log in via the CLI arguments:
```bash
docker compose -f docker-compose-dev.yaml exec redis redis-cli -a <your_redis_password>
```
> ⚠️ _Use this command only for local development._

#### 2. Useful Redis commands.
Once inside the CLI, you can use these basic commands to inspect the bot's state:
- `KEYS *` - List all keys currently stored in the database.
- `GET <key>` - View the content of a specific text key.
- `TTL <key>` - Check the remaining Time-To-Live for temporary keys.
- `DEL <key>` or `DEL <key1> <key2>` - Remove specific keys from the database.
- `UNLINK <huge_key>` - Asynchronously delete huge keys without blocking the main thread.
- `FLUSHDB` - Clear all data from current database.
- `FLUSHALL` - Clear all data from all databases.

#### 3. Exit the CLI.
Type `exit` or press `Ctrl + C` to return to your local terminal.
