import os
from dotenv import load_dotenv

# load_dotenv()

# # Токен вашего Telegram бота
# TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# # URL вашего сервиса в Cloud Run.
# WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://botolxkvartir-498789354610.us-east4.run.app")

# # API ключи
# GROK_API_KEY = os.getenv("GROK_API_KEY")
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# # Путь к файлу учетных данных Firebase
# FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "service-account.json")

# # ID администратора
# ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# # Учетные данные для Booking API
# BOOKING_PARTNER_ID = os.getenv("BOOKING_PARTNER_ID")
# BOOKING_SECRET = os.getenv("BOOKING_SECRET")

# # Токен для платежей
# STRIPE_TOKEN = os.getenv("STRIPE_TOKEN")

# Цены
WEEK_PRICE_USD = 10.0
MONTH_PRICE_USD = 20.0
WEEK_PRICE_STARS = 5
MONTH_PRICE_STARS = 10

# Кошельки для крипты
CRYPTO_WALLETS = {
    "TON": "EQ...your_ton_wallet",
    "USDT_TRC20": "T...your_usdt_trc20_wallet"
}

# Обязательно через os.getenv — Cloud Run передаёт только так
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/firebase.json")
# FIREBASE_CREDENTIALS_PATH = "/home/user/botolxkvartir/botolxkvartir-firebase-adminsdk-fbsvc-63c5cc654e.json"
# # Учетные данные Oxylabs (теперь из переменных окружения)
# OXYLABS_USERNAME = os.getenv("OXYLABS_USERNAME")
# OXYLABS_PASSWORD = os.getenv("OXYLABS_PASSWORD")

