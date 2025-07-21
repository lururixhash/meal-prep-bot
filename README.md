# 🍽️ Meal Prep Bot

Bot de Telegram inteligente para gestión de meal prep con batch cooking, rotación automática de recetas y asistencia con IA.

## 🌟 Características

- **Rotación automática de menús** cada 2 semanas
- **Cálculo de macros** con objetivos personalizables (145g proteína, 380g carbos, 100g grasa)
- **Generación de listas de compra** categorizadas automáticamente
- **Cronogramas de cocción optimizados** para Crockpot de 12L
- **Modificación inteligente de recetas** usando Claude AI basada en feedback
- **Base de datos JSON** simple y modificable
- **Interfaz conversacional** en español

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
git clone <url-del-repo>
cd meal-prep-bot
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar tokens de API

#### Telegram Bot Token
1. Habla con [@BotFather](https://t.me/BotFather) en Telegram
2. Crea un nuevo bot con `/newbot`
3. Guarda el token que te proporciona

#### Anthropic API Key
1. Ve a [console.anthropic.com](https://console.anthropic.com)
2. Crea una cuenta y genera una API key
3. Asegúrate de tener créditos disponibles

#### Configurar variables de entorno
```bash
# Opción 1: Variables de entorno
export TELEGRAM_TOKEN="tu_token_aqui"
export ANTHROPIC_API_KEY="tu_api_key_aqui"

# Opción 2: Modificar config.py directamente
# Edita config.py y reemplaza las variables correspondientes
```

### 4. Ejecutar el bot
```bash
python meal_bot.py
```

## 📱 Uso

### Comandos Principales

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/start` | Mensaje de bienvenida y ayuda | `/start` |
| `/menu` | Ver menú de la semana actual | `/menu` |
| `/recetas` | Listar todas las recetas | `/recetas` |
| `/buscar [consulta]` | Buscar o crear recetas con IA | `/buscar pollo curry` |
| `/compras` | Generar lista de compra | `/compras` |
| `/cronograma` | Ver cronograma de cocción | `/cronograma` |
| `/macros` | Resumen de macros diarios | `/macros` |
| `/rating [receta] [1-5] [comentario]` | Calificar y mejorar recetas | `/rating pollo_mediterraneo 4 menos sal` |
| `/favorito [receta]` | Marcar/desmarcar favorito | `/favorito quinoa_pilaf` |
| `/cambiar_semana [1-4]` | Cambiar semana manualmente | `/cambiar_semana 3` |

### Mensajes Conversacionales

El bot también entiende lenguaje natural:
- "No me gusta el cilantro en esta receta"
- "Quiero más recetas con pollo"
- "La carne quedó muy seca"
- "Hazme un menú vegetariano"

## 🍲 Sistema de Rotación

### Semanas 1-2: Mediterráneo/Mexicano
- **Proteínas:** Pollo Mediterráneo, Carne Deshebrada Mexicana
- **Legumbres:** Frijoles Negros, Garbanzos al Curry
- **Bases:** Quinoa Pilaf, Arroz Integral, Vegetales Asados, Huevos Duros

### Semanas 3-4: Asiático/Marroquí  
- **Proteínas:** Pollo Teriyaki, Cordero Marroquí
- **Legumbres:** Lentejas Rojas, Alubias Blancas
- **Bases:** Quinoa Pilaf, Arroz Integral, Vegetales Asados, Huevos Duros

## 🧮 Cálculo de Macros

El bot calcula automáticamente los macros diarios basándose en:
- **Proteínas:** 2 porciones por día
- **Legumbres:** 1.5 porciones por día  
- **Componentes base:** 1 porción de cada uno

### Objetivos por defecto:
- Proteína: 145g
- Carbohidratos: 380g
- Grasas: 100g
- Calorías: 2900

## 🛒 Lista de Compras Automática

Las listas se generan por categorías:
- 🥩 **Proteínas:** Carnes, aves, huevos
- 🫘 **Legumbres:** Frijoles, lentejas, garbanzos
- 🌾 **Cereales:** Arroz, quinoa, avena
- 🥬 **Vegetales:** Frescos y congelados
- 🧂 **Especias:** Condimentos y hierbas
- 🥛 **Lácteos:** Quesos, yogurt, leche
- 📦 **Otros:** Aceites, caldos, conservas

## ⏰ Cronograma de Cocción

### Sábado (2 tandas Crockpot)
1. Legumbres (6-8 horas)
2. Una proteína (4-8 horas)

### Domingo (Completar meal prep)
1. Segunda proteína (Crockpot)
2. Componentes base (Crockpot/horno/estufa)
3. Preparaciones rápidas

## 🤖 Integración con Claude AI

### Funcionalidades IA:
- **Búsqueda inteligente** de recetas existentes
- **Creación automática** de nuevas recetas
- **Modificación basada en feedback** para mejorar recetas
- **Respeto a preferencias** y restricciones alimentarias

### Ejemplo de modificación automática:
```
Usuario: /rating pollo_mediterraneo 3 quedó muy seco
Bot: 🤖 Receta modificada automáticamente:
- Reducido tiempo de cocción de 6-8h a 4-6h
- Agregado 1/2 taza de caldo extra para humedad
- Instrucción para revisar a las 4 horas
```

## 📁 Estructura de Archivos

```
meal-prep-bot/
├── meal_bot.py          # Bot principal
├── recipes.json         # Base de datos
├── config.py           # Configuración y tokens
├── requirements.txt    # Dependencias Python
├── README.md          # Este archivo
└── recipes_backup_*   # Backups automáticos
```

## 🔧 Personalización

### Modificar objetivos de macros:
Edita `recipes.json` → `user_preferences` → `macro_targets`

### Agregar nuevas recetas:
1. Usa `/buscar` para que Claude cree la receta
2. O edita manualmente `recipes.json` siguiendo el formato existente

### Cambiar horario de cocción:
Edita `recipes.json` → `user_preferences` → `cooking_schedule`

### Personalizar categorías de compras:
Edita `config.py` → `SHOPPING_CATEGORIES`

## 🐛 Solución de Problemas

### El bot no responde:
- Verifica que `TELEGRAM_TOKEN` esté correctamente configurado
- Revisa los logs en la consola para errores

### Error de Claude API:
- Verifica que `ANTHROPIC_API_KEY` sea válida
- Confirma que tienes créditos disponibles en tu cuenta
- Revisa tu límite de requests por minuto

### Error al cargar recipes.json:
- Verifica que el archivo exista y tenga formato JSON válido
- El bot creará un archivo por defecto si no existe

### Comandos no funcionan:
- Asegúrate de usar la sintaxis correcta: `/comando argumentos`
- Revisa que el bot tenga permisos para leer mensajes

## 📊 Logs y Monitoreo

El bot registra:
- Comandos ejecutados
- Errores de API
- Modificaciones de recetas
- Cambios en la base de datos

Los logs aparecen en la consola donde ejecutes `python meal_bot.py`

## 🔒 Backup y Seguridad

- **Backup automático:** Se crea antes de cada modificación a `recipes.json`
- **Archivos backup:** `recipes_backup_YYYYMMDD_HHMMSS.json`
- **Recuperación:** Copia un backup sobre `recipes.json` para restaurar

## 🚀 Funciones Avanzadas

### Rotación automática:
- Se activa automáticamente cada 14 días
- Cambia entre los 2 menús disponibles
- Mantiene historial de rotaciones

### Sistema de favoritos:
- Marca recetas preferidas con ⭐
- Visible en la lista de recetas
- Persiste entre rotaciones

### Historial de feedback:
- Guarda todos los comentarios
- Rastrea qué modificaciones se aplicaron
- Útil para análisis de preferencias

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama para tu feature
3. Haz commit de tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo LICENSE para detalles.

## ✨ Roadmap

### Próximas funcionalidades:
- [ ] Exportar recetas a PDF
- [ ] Integración con calendario
- [ ] Notificaciones de cocción
- [ ] Análisis nutricional avanzado
- [ ] Modo vegetariano/vegano
- [ ] Integración con apps de fitness
- [ ] Compartir recetas entre usuarios
- [ ] Modo batch cooking para familias grandes

## 📞 Soporte

Para soporte y preguntas:
- Abre un issue en GitHub
- Revisa la documentación en este README
- Verifica los logs para errores específicos

---

**¡Disfruta tu meal prep automatizado! 🍽️🤖**