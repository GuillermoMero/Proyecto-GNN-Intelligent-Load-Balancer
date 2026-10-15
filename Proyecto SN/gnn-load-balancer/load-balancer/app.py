import os
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# URLs de los servicios configuradas en el docker-compose
AUTH_URL = os.getenv("AUTH_URL", "http://auth-svc:5000")
PRODUCT_URL = os.getenv("PRODUCT_URL", "http://product-svc:5000")

# Lista de instancias del servicio de usuarios para el Round Robin
user_instances_env = os.getenv(
    "USER_INSTANCES", "http://user-svc-1:5000,http://user-svc-2:5000"
)
USER_INSTANCES = user_instances_env.split(",")

# Índice global para Round Robin
rr_index = 0


@app.route("/auth", methods=["GET"])
def proxy_auth():
  try:
    resp = requests.get(AUTH_URL)
    return jsonify(resp.json()), resp.status_code
  except Exception as e:
    return jsonify({"error": str(e)}), 500


@app.route("/users", methods=["GET"])
def proxy_users_round_robin():
  global rr_index
  if not USER_INSTANCES:
    return jsonify({"error": "No hay instancias de usuarios disponibles"}), 503

  # Seleccionar la instancia actual usando Round Robin
  target_instance = USER_INSTANCES[rr_index]
  # Actualizar el índice de manera cíclica
  rr_index = (rr_index + 1) % len(USER_INSTANCES)

  try:
    resp = requests.get(target_instance)
    data = resp.json()
    # Añadimos información de qué balanceador y ruta se usó
    data["load_balancer"] = "Round-Robin"
    return jsonify(data), resp.status_code
  except Exception as e:
    return jsonify(
        {"error": f"Fallo al conectar con la instancia {target_instance}", "detalles": str(e)}
    ), 500


@app.route("/products", methods=["GET"])
def proxy_products():
  try:
    resp = requests.get(PRODUCT_URL)
    return jsonify(resp.json()), resp.status_code
  except Exception as e:
    return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
  return jsonify({
      "message": (
          "Bienvenido al GNN Intelligent Load Balancer (Baseline Round Robin)"
      ),
      "endpoints_disponibles": ["/auth", "/users", "/products"],
  })


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8080)