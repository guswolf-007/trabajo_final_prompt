
# Imagen base oficial de Python
FROM python:3.12-slim

# Evita archivos .pyc y buffering raro en logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos requirements primero (mejor cache)
COPY requirements.txt .

# Instalamos dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del proyecto
COPY . .

# Cloud Run inyecta la variable PORT (normalmente 8080)
# ES CLAVE usar 0.0.0.0 y $PORT
CMD ["sh","-c","uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

