# Despliegue Alternativo - Sin Instalar gcloud Localmente

## 🚀 Método Recomendado: Google Cloud Shell

Google Cloud Shell es una terminal en la nube que ya tiene `gcloud` preinstalado y autenticado.

### Paso 1: Abrir Cloud Shell

1. Ve a: https://console.cloud.google.com
2. Asegúrate de estar en el proyecto `tiendalasmotos`
3. Haz clic en el ícono de **Cloud Shell** (>_) en la esquina superior derecha
4. Espera a que se active la terminal

### Paso 2: Subir el Código

En Cloud Shell, ejecuta:

```bash
# Clonar el repositorio (si está en GitHub)
# O subir los archivos manualmente usando el botón "Upload Files"

# Crear directorio
mkdir -p ~/Bot-TiendaLasMotos
cd ~/Bot-TiendaLasMotos
```

**Opción A: Si tienes GitHub configurado**
```bash
git clone https://github.com/TU-USUARIO/Bot-TiendaLasMotos.git .
```

**Opción B: Subir archivos manualmente**
1. En Cloud Shell, haz clic en el menú de tres puntos (⋮)
2. Selecciona "Upload"
3. Sube todos los archivos del proyecto

### Paso 3: Desplegar a Cloud Run

```bash
cd ~/Bot-TiendaLasMotos

gcloud run deploy bot-tiendalasmotos \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --project tiendalasmotos \
  --timeout 300 \
  --memory 512Mi \
  --cpu 1
```

### Paso 4: Obtener la URL

Al finalizar el despliegue, verás algo como:

```
Service [bot-tiendalasmotos] revision [bot-tiendalasmotos-00001-xxx] has been deployed and is serving 100 percent of traffic.
Service URL: https://bot-tiendalasmotos-XXXXXXXXXX-uc.a.run.app
```

**¡Esa es tu URL pública!** 🎉

---

## 📦 Método Alternativo 2: Comprimir y Subir

### Paso 1: Crear archivo ZIP

En tu Mac, ejecuta:

```bash
cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos
zip -r bot-tiendalasmotos.zip . -x "*.git*" -x "*__pycache__*"
```

### Paso 2: Subir a Cloud Shell

1. Abre Cloud Shell en https://console.cloud.google.com
2. Haz clic en el ícono de "Upload" (⋮ > Upload)
3. Selecciona `bot-tiendalasmotos.zip`
4. Espera a que termine la subida

### Paso 3: Descomprimir y Desplegar

En Cloud Shell:

```bash
mkdir -p ~/Bot-TiendaLasMotos
cd ~/Bot-TiendaLasMotos
unzip ~/bot-tiendalasmotos.zip

gcloud run deploy bot-tiendalasmotos \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --project tiendalasmotos
```

---

## 🌐 Método Alternativo 3: Cloud Console UI

### Paso 1: Ir a Cloud Run

1. Ve a: https://console.cloud.google.com/run
2. Asegúrate de estar en el proyecto `tiendalasmotos`
3. Haz clic en **"CREATE SERVICE"**

### Paso 2: Configurar el Servicio

1. **Source**: Selecciona "Continuously deploy from a repository (source or function)"
2. **Set up Cloud Build**: Conecta tu repositorio de GitHub
3. O selecciona "Deploy one revision from an existing container image" y sube el código

### Paso 3: Configuración

- **Service name**: `bot-tiendalasmotos`
- **Region**: `us-central1`
- **Authentication**: Allow unauthenticated invocations
- **Container port**: `8080`
- **Memory**: `512 MiB`
- **CPU**: `1`

### Paso 4: Deploy

Haz clic en **"CREATE"** y espera a que termine el despliegue.

---

## ✅ Verificación Post-Despliegue

Una vez desplegado, prueba:

```bash
# Health check
curl https://TU-SERVICE-URL/health

# Webhook verification
curl "https://TU-SERVICE-URL/webhook?hub.mode=subscribe&hub.verify_token=motos2026&hub.challenge=test123"
```

---

## 📝 Configurar en Meta

1. Ve a: https://developers.facebook.com
2. Selecciona tu app de WhatsApp Business
3. Ve a WhatsApp > Configuration
4. En **Webhook**:
   - **Callback URL**: `https://TU-SERVICE-URL/webhook`
   - **Verify Token**: `motos2026`
5. Haz clic en **"Verify and Save"**
6. Suscríbete a los eventos de mensajes

---

## 🎯 Recomendación

**Usa Cloud Shell** - Es la forma más rápida y no requiere instalar nada en tu Mac.

¿Necesitas ayuda con alguno de estos métodos?
