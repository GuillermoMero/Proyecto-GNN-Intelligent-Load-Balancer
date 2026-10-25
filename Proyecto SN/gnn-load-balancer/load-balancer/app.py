import os
import threading
import time
from flask import Flask, jsonify, request
import requests
from intelligent_router import IntelligentLoadBalancerEnv

app = Flask(__name__)

# URLs de los servicios configuradas en el docker-compose
AUTH_URL = os.getenv("AUTH_URL", "http://auth-svc:5001")
COURSE_URL = os.getenv("COURSE_URL", "http://course-svc:5003")

# Lista de instancias del servicio de usuarios (puerto 5000 interno)
USER_INSTANCES = ["http://user-svc-1:5000", "http://user-svc-2:5000"]

# --- Estado para Round Robin ---
rr_index = 0
rr_lock = threading.Lock()

# --- Estado para Least Connections ---
active_connections = {instance: 0 for instance in USER_INSTANCES}
lc_lock = threading.Lock()

# --- Entorno Inteligente (GNN + RL) ---
gnn_env = IntelligentLoadBalancerEnv(USER_INSTANCES)
gnn_lock = threading.Lock()


@app.route("/api/sga/login", methods=["POST", "GET"])
def proxy_auth():
    try:
        resp = requests.request(
            method=request.method,
            url=AUTH_URL + "/sga/login",
            json=request.get_json(silent=True),
            headers={k: v for k, v in request.headers if k != 'Host'}
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Endpoint para Round Robin
@app.route("/api/rr/student/record", methods=["GET", "POST"])
def proxy_round_robin():
    global rr_index
    with rr_lock:
        target_instance = USER_INSTANCES[rr_index]
        rr_index = (rr_index + 1) % len(USER_INSTANCES)

    try:
        resp = requests.request(
            method=request.method,
            url=target_instance + "/student/record",
            json=request.get_json(silent=True),
            headers={k: v for k, v in request.headers if k != 'Host'}
        )
        data = resp.json()
        data["load_balancer"] = "Round-Robin"
        data["handled_by_instance"] = target_instance
        return jsonify(data), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Fallo al conectar con {target_instance}", "detalles": str(e)}), 500


# Endpoint para Least Connections
@app.route("/api/lc/student/record", methods=["GET", "POST"])
def proxy_least_connections():
    with lc_lock:
        target_instance = min(USER_INSTANCES, key=lambda inst: active_connections[inst])
        active_connections[target_instance] += 1

    try:
        resp = requests.request(
            method=request.method,
            url=target_instance + "/student/record",
            json=request.get_json(silent=True),
            headers={k: v for k, v in request.headers if k != 'Host'}
        )
        data = resp.json()
        data["load_balancer"] = "Least-Connections"
        data["handled_by_instance"] = target_instance
        return jsonify(data), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Fallo al conectar con {target_instance}", "detalles": str(e)}), 500
    finally:
        with lc_lock:
            active_connections[target_instance] = max(0, active_connections[target_instance] - 1)


# Endpoint Inteligente (GNN + RL Enrutamiento)
@app.route("/api/gnn/student/record", methods=["GET", "POST"])
def proxy_gnn_intelligent():
    start_time = time.time()
    
    with gnn_lock:
        state = gnn_env.get_state()
        target_instance = gnn_env.select_action(state)
        gnn_env.update_metrics(target_instance, 0, active_delta=1)

    try:
        resp = requests.request(
            method=request.method,
            url=target_instance + "/student/record",
            json=request.get_json(silent=True),
            headers={k: v for k, v in request.headers if k != 'Host'}
        )
        elapsed_ms = (time.time() - start_time) * 1000
        
        with gnn_lock:
            reward = gnn_env.compute_reward(elapsed_ms)
            gnn_env.update_metrics(target_instance, elapsed_ms, active_delta=-1)

        data = resp.json()
        data["load_balancer"] = "GNN-RL-Intelligent"
        data["handled_by_instance"] = target_instance
        data["reward"] = reward
        return jsonify(data), resp.status_code
    except Exception as e:
        with gnn_lock:
            gnn_env.update_metrics(target_instance, 0, active_delta=-1)
        return jsonify({"error": f"Fallo al conectar con {target_instance}", "detalles": str(e)}), 500


@app.route("/api/courses/enroll", methods=["POST", "GET"])
def proxy_courses():
    try:
        resp = requests.request(
            method=request.method,
            url=COURSE_URL + "/courses/enroll",
            json=request.get_json(silent=True),
            headers={k: v for k, v in request.headers if k != 'Host'}
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "GNN Intelligent Load Balancer - SGA ESPOL (Entorno RL Activo)",
        "endpoints_disponibles": [
            "/api/sga/login",
            "/api/rr/student/record (Round Robin)",
            "/api/lc/student/record (Least Connections)",
            "/api/gnn/student/record (GNN + RL Intelligent)",
            "/api/courses/enroll"
        ],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)