# Configuración de Railway para Meal Prep Bot

Este documento explica cómo configurar el bot para funcionar con webhooks en Railway, resolviendo el error 409.

## Variables de Entorno Requeridas en Railway

### Variables Obligatorias
```
TELEGRAM_TOKEN=tu_token_de_telegram
ANTHROPIC_API_KEY=tu_api_key_de_anthropic
USE_WEBHOOK=true
WEBHOOK_URL=https://tu-app.railway.app
```

### Variables Opcionales
```
WEBHOOK_PATH=/webhook/tu_token_de_telegram
PORT=5000
```

## Pasos de Configuración en Railway

1. **Deploy del Proyecto**
   - Conecta tu repositorio de GitHub a Railway
   - Railway detectará automáticamente que es una aplicación Python

2. **Configurar Variables de Entorno**
   - Ve a tu proyecto en Railway
   - Click en "Variables"
   - Agrega las variables mencionadas arriba
   - Para `WEBHOOK_URL`, usa la URL que Railway te proporciona (ej: `https://meal-prep-bot-production.railway.app`)

3. **Verificar Deployment**
   - El bot debería iniciarse automáticamente
   - Puedes verificar los logs en Railway para confirmar que el webhook se configuró correctamente
   - Busca el mensaje: "Webhook configurado: https://tu-app.railway.app/webhook/tu_token"

## Resolución del Error 409

El modo webhook elimina el error 409 porque:
- ✅ No usa polling (getUpdates)
- ✅ Railway envía las actualizaciones directamente al bot
- ✅ No hay competencia entre múltiples instancias
- ✅ Es más eficiente en recursos

## Health Check

El bot incluye un endpoint de health check en `/health` que Railway puede usar para monitorear el estado de la aplicación.

## Desarrollo Local

Para desarrollo local, puedes mantener `USE_WEBHOOK=false` y el bot funcionará en modo polling tradicional.

## Troubleshooting

Si tienes problemas:
1. Verifica que `WEBHOOK_URL` no termine en `/`
2. Asegúrate de que `USE_WEBHOOK=true` esté configurado correctamente
3. Revisa los logs de Railway para ver mensajes de error
4. Usa `/health` para verificar que la aplicación está corriendo