# Configuration file for the Meal Prep Bot
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Telegram Bot Token - Get from @BotFather
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# Anthropic API Key - Get from console.anthropic.com
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'YOUR_ANTHROPIC_API_KEY_HERE')

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