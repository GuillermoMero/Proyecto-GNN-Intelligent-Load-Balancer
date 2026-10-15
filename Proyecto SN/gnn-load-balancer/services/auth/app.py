from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def auth_home():
  return jsonify(
      {"service": "auth-svc", "status": "active", "message": "Token validado"}
  )


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)