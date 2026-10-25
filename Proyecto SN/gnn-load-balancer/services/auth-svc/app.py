from flask import Flask, jsonify, request
import redis
import os

app = Flask(__name__)
redis_host = os.getenv('REDIS_HOST', 'redis')
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

@app.route('/sga/login', methods=['POST'])
def sga_login():
    data = request.json or {}
    username = data.get('username', 'estudiante')
    
    # Simula validación de credenciales institucionales
    token = f"token-espol-{username}-2026"
    r.set(token, username, ex=3600) # Guarda sesión en Redis por 1 hora
    
    return jsonify({
        "status": "success",
        "message": f"Acceso exitoso al SGA para {username}",
        "session_token": token
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)