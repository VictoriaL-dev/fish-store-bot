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
- [🔐 Managing PostgreSQL via Adminer](#-managing-postgresql-via-adminer-_docker-only_)
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
├── database.py         # Handles connection pool setup for Redis
├── keyboards.py        # Centralized module for reusable reply and inline menu button configurations
├── strapi_api.py       # Client for executing requests against the Strapi REST API
├── logging_config.py   # Root logging configuration for the Python bot
├── main.py             # Main entry point for the Python bot
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
- Strapi [Collection Types](https://docs.strapi.io/cms/features/content-type-builder): 
  - Product: title, description, picture, price

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
STRAPI_TOKEN="your_full_access_or_read_only_token"
STRAPI_URL="http://localhost:1337"

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

### Frontend Setup (Python Bot)
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
python main.py
```

#### 4. Test the bot: 
Open Telegram, find your bot, and send the `/start` command.


## 🔐 Managing PostgreSQL via Adminer _(Docker only)_
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
