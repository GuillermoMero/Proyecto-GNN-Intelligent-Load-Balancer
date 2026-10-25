from flask import Flask, jsonify, request
import os
import time
import redis

app = Flask(__name__)

# Configuración de Redis y congestión simulada...
# ...

@app.route('/student/record', methods=['GET', 'POST'])
def student_record():
    # Si la réplica tiene activada la congestión artificial (user-svc-2)
    if os.getenv('SIMULATE_CONGESTION', 'false') == 'true':
        time.sleep(0.4) # Retraso simulado de 400ms

    replica_id = os.getenv('REPLICA_ID', 'unknown')
    return jsonify({
        "status": "success",
        "replica": replica_id,
        "message": "Historial académico consultado con éxito"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)