# ✅ CÓDIGO SUBIDO EXITOSAMENTE A GITHUB

## 🎉 Push Completado

**Repository**: https://github.com/tobiasgaitan/Bot-TiendaLasMotos

**Estadísticas del Push**:
- ✅ 36 objetos enviados
- ✅ 32.01 KB transferidos
- ✅ Branch `main` creado y trackeado
- ✅ 2 commits totales

---

## 📥 PRÓXIMO PASO: Clonar en Google Cloud Shell

### Paso 1: Abrir Cloud Shell

Ve a: https://console.cloud.google.com/

Haz clic en el ícono de **Cloud Shell** (terminal) en la esquina superior derecha.

---

### Paso 2: Clonar el Repositorio

Copia y pega estos comandos en Cloud Shell:

```bash
# Clonar repositorio
git clone https://github.com/tobiasgaitan/Bot-TiendaLasMotos.git

# Navegar al proyecto
cd Bot-TiendaLasMotos

# Verificar archivos
ls -la
ls -la scripts/
ls -la app/core/
```

**Deberías ver**:
- ✅ `scripts/init_v6_config.py`
- ✅ `app/core/config_loader.py`
- ✅ `app/main.py`
- ✅ `deploy.sh`

---

### Paso 3: Inicializar Configuración V6.0 en Firestore

```bash
# Ejecutar script de inicialización (UNA VEZ)
python3 scripts/init_v6_config.py
```

**Salida Esperada**:
```
============================================================
V6.0 Configuration Initialization
Tienda Las Motos - WhatsApp Bot
============================================================

🔥 Connecting to Firestore...
✅ Connected to Firestore

📝 Initializing Sebas personality configuration...
✅ Sebas personality configuration created
📝 Initializing routing rules...
✅ Routing rules configuration created
📝 Initializing financial configuration...
✅ Financial configuration created
📝 Initializing catalog configuration...
✅ Catalog configuration created

🔍 Verifying configuration...
  ✅ sebas_personality: OK
  ✅ routing_rules: OK
  ✅ financiera: OK
  ✅ catalog_config: OK

✅ All V6.0 configuration documents created successfully!
```

---

### Paso 4: Desplegar a Cloud Run

```bash
# Desplegar aplicación
./deploy.sh
```

**Tiempo estimado**: 2-3 minutos

---

### Paso 5: Verificar Deployment

```bash
# Obtener URL del servicio
gcloud run services describe bot-tiendalasmotos \
  --region=us-central1 \
  --format='value(status.url)'

# Probar health endpoint
curl https://[YOUR-SERVICE-URL]/health
```

**Respuesta Esperada**:
```json
{
  "status": "healthy",
  "service": "Tienda Las Motos Backend",
  "version": "6.0.0",
  "v6_config": {
    "sebas_model": "gemini-2.0-flash",
    "routing_keywords_loaded": 17,
    "catalog_config_items": 4
  }
}
```

---

### Paso 6: Ver Logs en Tiempo Real

```bash
# Ver logs de Cloud Run
gcloud run services logs read bot-tiendalasmotos --limit=50
```

**Busca estas líneas**:
- ✅ "🧠 Loading V6.0 dynamic configuration..."
- ✅ "✅ Sebas personality loaded (model: gemini-2.0-flash)"
- ✅ "✅ Routing rules loaded (17 financial keywords)"
- ✅ "✅ Financial configuration loaded"

---

## 🔄 Workflow de Desarrollo (Futuro)

### En tu Mac (Local):

```bash
# Hacer cambios al código
# ...

# Commit y push
git add .
git commit -m "descripción de cambios"
git push origin main
```

### En Cloud Shell:

```bash
# Actualizar código
cd ~/Bot-TiendaLasMotos
git pull origin main

# Re-desplegar
./deploy.sh
```

---

## 📊 Verificar en Firestore Console

Ve a: https://console.firebase.google.com/project/tiendalasmotos/firestore

Navega a la colección `configuracion/` y verifica que existen:
- ✅ `sebas_personality`
- ✅ `routing_rules`
- ✅ `financiera`
- ✅ `catalog_config`

---

## ✅ Checklist Final

- [x] Código subido a GitHub
- [ ] Repositorio clonado en Cloud Shell
- [ ] Script `init_v6_config.py` ejecutado
- [ ] Configuración verificada en Firestore
- [ ] Aplicación desplegada a Cloud Run
- [ ] Health endpoint respondiendo con V6.0
- [ ] Logs confirmando carga de configuración

---

## 🆘 Troubleshooting

### Error: "Permission denied"
```bash
# Configurar credenciales de GitHub en Cloud Shell
git config --global user.name "Tobias Gaitan"
git config --global user.email "tu-email@example.com"
```

### Error: "Firestore permission denied"
Verifica que el proyecto GCP está configurado:
```bash
gcloud config set project tiendalasmotos
```

### Error: "Module not found"
Instala dependencias:
```bash
pip3 install -r requirements.txt
```

---

## 🎯 ¡Listo para Producción!

Una vez completados todos los pasos, tu bot V6.0 estará:
- ✅ Desplegado en Cloud Run
- ✅ Configurado dinámicamente desde Firestore
- ✅ Usando Gemini 2.0 Flash
- ✅ Con tasas financieras configurables
- ✅ Sincronizado con GitHub para futuras actualizaciones
