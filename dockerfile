# 1️⃣  Crear el archivo Dockerfile con el contenido necesario
@"
# ----------  Dockerfile para Railway  ----------
# Usa una imagen ligera de Python 3.11 (puedes cambiar la versión si tu proyecto necesita otra)
FROM python:3.11-slim

# Evita que pip pregunte interactivamente y usa caché de paquetes
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Instala dependencias del sistema que puedan necesitarse (git, curl, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crea y usa un directorio de trabajo
WORKDIR /app

# Copia sólo los archivos necesarios para instalar dependencias
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia el resto del código
COPY . .

# En Railway el volumen persistente se monta en /railway/volume
# Vamos a crear un alias para que el código use esa ruta
ENV RAILWAY_VOLUME=/railway/volume

# (Opcional) Exponer un puerto si tu bot abre un servidor HTTP.
# En este caso no es necesario, pero si lo haces, descomenta la línea siguiente:
# EXPOSE 8000

# Comando por defecto: ejecuta el script que lanza el bot.
# Cambia `src.main` por el módulo que realmente inicia el scheduler.
CMD ["python", "-m", "src.main"]
"@ | Set-Content -Path Dockerfile -Encoding UTF8