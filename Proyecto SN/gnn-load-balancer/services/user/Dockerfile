FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir flask
# Copiaremos el código fuente de cada servicio más adelante
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]