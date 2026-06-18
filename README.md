# 🐟 Telegram Fish Store Bot
A Telegram bot tailored for a fish store. This application bridges a sleek Telegram customer interface with a powerful 
**Strapi CMS** backend for real-time inventory management, product updates, and order processing. By leveraging **Redis**, 
the bot maintains lightning-fast user session states (FSM), allowing customers to seamlessly browse products, manage 
their shopping carts, and place orders directly from their phones.


## 📌 Table of Contents
- [⚙️ Tech Stack](#-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🛠️ Installation & Setup](#-installation--setup)
- [🚀 Quick Start Guide](#-quick-start-guide)
- [🔑 Strapi v5 Backend Configuration Guide](#-strapi-v5-backend-configuration-guide)
- [🔐 Managing PostgreSQL via Adminer](#-managing-postgresql-via-adminer-docker-only)
- [🔍 Inspecting Redis Data via Docker](#-inspecting-redis-data-via-docker)


## ⚙️ Tech Stack
- **Python 3.10+**: Core bot logic.
- **Node.js v20/v22/v24**: Runtime environment for running the Strapi CMS backend.
- **[Strapi](https://github.com/strapi/strapi) v5**: Headless CMS for managing products.
- **Docker & Docker Compose**: For containerizing PostgreSQL and Redis services _(optional)_.
- **Database**: Supports PostgreSQL (via Docker) and SQLite.
- **python-telegram-bot v13.15**: Framework for Telegram Bot API.
- **Redis**: In-memory data structure store for managing user conversation states (via Docker or local).


## 📁 Project Structure
```text
.
├── config/             # Strapi configuration files
├── database/           # Local database migration files
├── dist/               # Production build outputs
├── public/             # Static assets for Strapi
├── scripts/            # Automation and helper scripts
├── src/                # Strapi backend source code
├── types/              # TypeScript type definitions
├── bot/                # Core bot logic
│   ├── database.py         # Connection pool setup for Redis
│   ├── keyboards.py        # Centralized module for reusable reply and inline menu button configurations
│   ├── screens.py          # Bot screens management and UI rendering
│   ├── strapi_api.py       # Client for executing requests against the Strapi REST API
│   ├── logging_config.py   # Logging configuration for the Python bot
│   └── main.py             # Main entry point for the Python bot
├── requirements.txt    # Python dependencies
├── package.json        # Node.js project manifest and Strapi dependencies
├── package-lock.json   # Locked versions of Node.js dependencies
└── tsconfig.json       # TypeScript configuration
```


## 🛠️ Installation & Setup

### Prerequisites:
- [Node.js](https://nodejs.org/en) (v20, v22, or v24)
- [Python](https://www.python.org/) (v3.10 or higher)
- Redis server (running [locally](https://redis-docs.ru/operate/oss_and_stack/install/install-redis/) or via [Docker](https://www.docker.com/products/docker-desktop/))
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Basic knowledge of [Strapi CMS](https://docs.strapi.io/cms/quick-start)
- Strapi API [token](https://docs.strapi.io/cms/features/api-tokens)

### Common Setup:
#### 1. Clone the repository:
```bash
git clone https://github.com/VictoriaL-dev/fish-store-bot.git
cd fish-store-bot
```

#### 2. Configure environment variables:
Create a `.env` file in the root directory based on `.env.example` and configure your database choice (toggle between `sqlite` and `postgres`):
```dotenv
# Strapi server
HOST=0.0.0.0
PORT=1337

# Strapi secrets
APP_KEYS="toBeModified1,toBeModified2"
API_TOKEN_SALT="tobemodified"
ADMIN_JWT_SECRET="tobemodified"
TRANSFER_TOKEN_SALT="tobemodified"
ENCRYPTION_KEY="tobemodified"

# Strapi API
STRAPI_TOKEN="your_full_access_or_custom_token"
STRAPI_URL="http://localhost:1337"
STRAPI_USER_ROLE=1  # Authenticated user role id
STRAPI_USER_PASSWORD="your_password_for_strapi_user_creation"

# Database
DATABASE_CLIENT=postgres  # Replace with 'sqlite' if you don't want to use PostgreSQL
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5433
DATABASE_NAME=postgres_db
DATABASE_USERNAME=postgres_user
DATABASE_PASSWORD="your_postgres_password"
DATABASE_SSL=false
DATABASE_FILENAME=.tmp/data.db
JWT_SECRET="tobemodified"

# Adminer
ADMINER_PORT=8080

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD="your_redis_password"

# Telegram
TG_BOT_TOKEN="your_bot_token"
```

### Backend Setup (Strapi)
#### 1. Install Node dependencies:
```bash
npm install
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
#### 1. Spin up PostgreSQL and Redis using Docker _(or, if you're not using Docker, SQLite and locally running Redis instead)_:
```bash
docker-compose -f docker-compose-dev.yaml up -d
```

#### 2. Start the Strapi development server:
```bash
npm run develop
```
You can access the admin panel at [http://localhost:1337/admin](http://localhost:1337/admin).

#### 3. Run the Telegram bot:
Open a new terminal, activate your Python virtual environment, and start the bot:
```bash
cd bot
python main.py
```

#### 4. Test the bot: 
Open Telegram, find your bot, and send the `/start` command.


## 🔑 Strapi v5 Backend Configuration Guide
To ensure the Telegram bot can successfully communicate with Strapi v5, you need to configure specific roles and 
permissions in your Strapi Admin Panel [http://localhost:1337/admin](http://localhost:1337/admin).

### How to Find the Authenticated Role ID
When the bot automatically registers a new customer using their email during checkout, it forces Strapi to assign them 
to a default system role (typically Authenticated). To find the exact ID of this role for your strapi_api configuration:
#### 1. Navigate to Settings ➔ Roles (under the Users & Permissions Plugin section).
#### 2. Click on the Authenticated role to open its settings.
#### 3. Look at your browser's address bar. The URL will end with a specific number (e.g., `.../users-permissions/roles/1`).
#### 4. This number is your Authenticated Role ID. Set this value in your bot's `.env` file.

### Permissions Required for a Custom API Token or Full Access Token
If you are connecting your Telegram bot to Strapi using a Custom API Token (generated via Settings ➔ API Tokens with 
token type set to Custom), you must explicitly check the boxes for the following permissions at the bottom of the token 
settings page:

#### 📦 Core Store Models (Custom Content-Types):
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
`Users-Permissions` (under the User subsection):
  - find (allows looking up if a customer's email is already registered)
  - create (allows registering a new user profile with their email during checkout)

`Upload` (Media Library plugin):
  - find (allows the bot to deep-populate and extract relative URLs for fish images stored inside product relations)


## 🔐 Managing PostgreSQL via Adminer (Docker only)
This project includes `Adminer`, a lightweight and fast database management interface available via web browser. It 
is configured to run inside a Docker container alongside PostgreSQL.

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
docker-compose -f docker-compose-dev.yaml exec redis redis-cli
```

#### 2. Authenticate:
```text
127.0.0.1:6379> AUTH your_redis_password
```

#### 3. Useful Redis commands.
Once inside the CLI, you can use these basic commands to inspect the bot's state:
- `KEYS *` - List all keys currently stored in the database.
- `GET <key>` - View the content of a specific text key.
- `TTL <key>` - Check the remaining Time-To-Live for temporary keys.
- `DEL <key>` or `DEL <key1> <key2>` - Remove specific keys from the database.
- `UNLINK <huge_key>` - Asynchronously delete huge keys without blocking the main thread.
- `FLUSHDB` - Clear all data from current database.
- `FLUSHALL` - Clear all data from all databases.

#### 4. Exit the CLI.
Type `exit` or press `Ctrl + C` to return to your local terminal.
