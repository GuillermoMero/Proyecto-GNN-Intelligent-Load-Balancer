FROM python:3.9-slim

WORKDIR /app

# Copiar e instalar dependencias primero (aprovecha el caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del microservicio
COPY . .

# Exponer el puerto correspondiente (5001 para auth, 5002 para user, 5003 para course)
EXPOSE 5001 

CMD ["python", "app.py"]