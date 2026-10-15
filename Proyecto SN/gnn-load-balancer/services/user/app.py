import os
from flask import Flask, jsonify

app = Flask(__name__)
INSTANCE_ID = os.getenv("INSTANCE_ID", "user-svc-unknown")


@app.route("/", methods=["GET"])
def user_home():
  return jsonify({
      "service": "user-svc",
      "instance": INSTANCE_ID,
      "status": "active",
      "message": f"Respuesta desde la instancia {INSTANCE_ID}",
  })


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)