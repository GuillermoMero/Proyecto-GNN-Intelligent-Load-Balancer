from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def product_home():
  return jsonify({
      "service": "product-svc",
      "status": "active",
      "message": "Catálogo de productos obtenido",
  })


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)