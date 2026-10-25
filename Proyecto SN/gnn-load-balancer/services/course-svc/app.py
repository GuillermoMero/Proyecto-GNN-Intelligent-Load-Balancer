from flask import Flask, jsonify, request
import redis
import os

app = Flask(__name__)
redis_host = os.getenv('REDIS_HOST', 'redis')
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

@app.route('/courses/enroll', methods=['POST'])
def enroll_course():
    data = request.json or {}
    course_code = data.get('course_code', 'FIEC0100') # Ej: Sistemas en la Nube
    
    # Control de cupos atómico usando Redis
    cupos_key = f"cupos:{course_code}"
    
    # Si no existe la llave, inicializamos con 30 cupos
    if not r.exists(cupos_key):
        r.set(cupos_key, 30)
        
    current_cupos = int(r.get(cupos_key))
    
    if current_cupos > 0:
        r.decr(cupos_key)
        return jsonify({
            "status": "Matriculado con éxito",
            "course": course_code,
            "cupos_restantes": int(r.get(cupos_key))
        }), 200
    else:
        return jsonify({
            "status": "Error: Materia sin cupos disponibles",
            "course": course_code
        }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)