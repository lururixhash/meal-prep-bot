# Configuration file for the Meal Prep Bot
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Telegram Bot Token - Get from @BotFather
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# Anthropic API Key - Get from console.anthropic.com
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'YOUR_ANTHROPIC_API_KEY_HERE')

# Webhook configuration
WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)  # e.g., 'https://your-app.railway.app'
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', f'/webhook/{TELEGRAM_TOKEN}')
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'

# Bot settings
BOT_USERNAME = "meal_prep_bot"
DATABASE_FILE = "recipes.json"
BACKUP_PREFIX = "recipes_backup_"

# Default user preferences
DEFAULT_MACRO_TARGETS = {
    "protein": 145,
    "carbs": 380,
    "fat": 100,
    "calories": 2900
}

# Cooking schedule template
DEFAULT_COOKING_SCHEDULE = {
    "saturday": ["legumes_1", "protein_2"],
    "sunday": ["legumes_2", "protein_1", "base_components"]
}

# Recipe categories
RECIPE_CATEGORIES = ["protein", "legume", "base", "vegetable", "sauce"]

# Shopping list categories
SHOPPING_CATEGORIES = {
    "proteinas": ["pollo", "carne", "pescado", "huevos", "tofu"],
    "legumbres": ["lentejas", "garbanzos", "frijoles", "judias"],
    "cereales": ["arroz", "quinoa", "avena", "pasta"],
    "vegetales": ["cebolla", "ajo", "tomate", "pimiento", "zanahoria"],
    "especias": ["sal", "pimienta", "comino", "oregano", "tomillo"],
    "lacteos": ["queso", "yogurt", "leche"],
    "otros": ["aceite", "vinagre", "caldos"]
}

# Macro calculation constants
ACTIVITY_FACTORS = {
    "sedentario": 1.2,
    "ligero": 1.375,
    "moderado": 1.55,
    "intenso": 1.725,
    "atletico": 1.9
}

PHYSICAL_WORK_BONUS = {
    "oficina": 0,
    "ligero": 200,      # Trabajo de pie, caminar ocasional
    "moderado": 400,    # Trabajo físico moderado, cargas ligeras
    "pesado": 600       # Construcción, carga pesada, trabajo manual intenso
}

MACRO_DISTRIBUTIONS = {
    "bajar_grasa": {"protein": 0.35, "carbs": 0.40, "fat": 0.25},
    "subir_masa": {"protein": 0.30, "carbs": 0.45, "fat": 0.25},
    "mantener": {"protein": 0.30, "carbs": 0.40, "fat": 0.30}
}

CALORIC_ADJUSTMENTS = {
    "bajar_grasa": -0.15,  # -15% del TDEE
    "subir_masa": 0.15,    # +15% del TDEE
    "mantener": 0.0        # TDEE exacto
}

# Validation ranges
VALIDATION_RANGES = {
    "peso": (30, 300),      # kg
    "altura": (120, 220),   # cm
    "edad": (15, 100)       # años
}