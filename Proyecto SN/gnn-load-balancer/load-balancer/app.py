import os
import time
import random
import threading
import requests
from flask import Flask, jsonify, request, render_template

from intelligent_router import IntelligentLoadBalancerEnv

# psutil: CPU/RAM del propio balanceador (nodo "gateway" del grafo)
try:
    import psutil
    _proc = psutil.Process(os.getpid())
    _proc.cpu_percent(interval=None)  # primera llamada de calibración
except Exception:
    _proc = None

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuración (vía variables de entorno del docker-compose)
# ---------------------------------------------------------------------------
AUTH_URL = os.getenv("AUTH_URL", "http://auth-svc:5001")
COURSE_URL = os.getenv("COURSE_URL", "http://course-svc:5003")
USER_INSTANCES = [
    u.strip() for u in os.getenv(
        "USER_INSTANCES", "http://user-svc-1:5000,http://user-svc-2:5000"
    ).split(",") if u.strip()
]
UPSTREAM_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "5"))
POLL_INTERVAL = float(os.getenv("METRICS_POLL_INTERVAL", "1.0"))

# Headers que no deben reenviarse tal cual al servicio destino
HOP_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


def clean_headers():
    return {k: v for k, v in request.headers if k.lower() not in HOP_HEADERS}


# ---------------------------------------------------------------------------
# Estado de cada estrategia
# ---------------------------------------------------------------------------
rr_index = 0
rr_lock = threading.Lock()

lc_active = {i: 0 for i in USER_INSTANCES}
lc_lock = threading.Lock()

request_counters = {i: {"rr": 0, "lc": 0, "gnn": 0} for i in USER_INSTANCES}
counter_lock = threading.Lock()

gnn_env = IntelligentLoadBalancerEnv(USER_INSTANCES)


def count(instance, algo):
    with counter_lock:
        request_counters[instance][algo] += 1


# ---------------------------------------------------------------------------
# Poller: lee /metrics de TODOS los nodos del grafo y alimenta su estado
# ---------------------------------------------------------------------------
def poll_metrics():
    # nombre del nodo en el grafo -> URL base del servicio
    targets = {"auth-svc": AUTH_URL, "course-svc": COURSE_URL}
    targets.update({u: u for u in USER_INSTANCES})
    s = requests.Session()
    while True:
        for node, url in targets.items():
            try:
                m = s.get(url + "/metrics", timeout=1).json()
                gnn_env.set_remote(node, m.get("cpu_percent", 0.0), m.get("mem_mb", 0.0))
                # auth-svc mide la latencia de su dependencia (redis)
                if node == "auth-svc" and "redis_ping_ms" in m:
                    gnn_env.set_latency("redis", m["redis_ping_ms"])
            except Exception:
                pass
        # el propio balanceador es el nodo "gateway"
        if _proc is not None:
            gnn_env.set_remote("gateway", _proc.cpu_percent(interval=None),
                               _proc.memory_info().rss / (1024 * 1024))
        # réplicas sin tráfico reciente: su latencia decae para re-probarlas
        gnn_env.decay_stale()
        time.sleep(POLL_INTERVAL)


threading.Thread(target=poll_metrics, daemon=True).start()


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("sga_portal.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/info", methods=["GET"])
def api_info():
    return jsonify({
        "message": "GNN Intelligent Load Balancer - SGA ESPOL",
        "user_instances": USER_INSTANCES,
        "endpoints": [
            "/api/sga/login",
            "/api/rr/student/record (Round Robin)",
            "/api/lc/student/record (Least Connections)",
            "/api/gnn/student/record (GNN + RL)",
            "/api/gnn/state (estado del grafo y Q-values)",
            "/api/gnn/reset (reinicia el aprendizaje)",
            "/api/stats (peticiones por instancia y algoritmo)",
            "/api/courses/enroll",
        ],
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Observabilidad
# ---------------------------------------------------------------------------
@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Alimenta el dashboard con el estado real del grafo GNN."""
    snap = gnn_env.snapshot()
    with counter_lock:
        totals = {i: sum(c.values()) for i, c in request_counters.items()}
    return jsonify({
        "instances": USER_INSTANCES,
        "active_connections": {i: snap["node_state"][i]["active_connections"] for i in USER_INSTANCES},
        "total_requests": totals,
        "q_values": snap["q_values"],
        "last_state": snap["node_state"],
    })


@app.route("/api/gnn/state", methods=["GET"])
def gnn_state():
    return jsonify(gnn_env.snapshot())


@app.route("/api/gnn/reset", methods=["POST"])
def gnn_reset():
    gnn_env.reset()
    return jsonify({"status": "reset"})


@app.route("/api/stats", methods=["GET", "DELETE"])
def stats():
    """Peticiones atendidas por cada instancia y algoritmo. DELETE las pone en 0."""
    with counter_lock:
        if request.method == "DELETE":
            for c in request_counters.values():
                for k in c:
                    c[k] = 0
        return jsonify(request_counters)


# ---------------------------------------------------------------------------
# Proxies a servicios sin balanceo
# ---------------------------------------------------------------------------
def simple_proxy(url):
    try:
        resp = requests.request(
            method=request.method, url=url,
            json=request.get_json(silent=True),
            headers=clean_headers(), timeout=UPSTREAM_TIMEOUT,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/sga/login", methods=["POST", "GET"])
def proxy_auth():
    return simple_proxy(AUTH_URL + "/sga/login")


@app.route("/api/courses/enroll", methods=["POST", "GET"])
def proxy_courses():
    return simple_proxy(COURSE_URL + "/courses/enroll")


# ---------------------------------------------------------------------------
# Reenvío a la instancia elegida (común a los tres algoritmos)
# ---------------------------------------------------------------------------
def forward_to_user(target):
    return requests.request(
        method=request.method,
        url=target + "/student/record",
        json=request.get_json(silent=True),
        headers=clean_headers(),
        timeout=UPSTREAM_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Round Robin (baseline obligatorio)
# ---------------------------------------------------------------------------
@app.route("/api/rr/student/record", methods=["GET", "POST"])
def proxy_round_robin():
    global rr_index
    with rr_lock:
        target = USER_INSTANCES[rr_index]
        rr_index = (rr_index + 1) % len(USER_INSTANCES)
    try:
        resp = forward_to_user(target)
        data = resp.json()
        data.update(load_balancer="Round-Robin", handled_by_instance=target)
        count(target, "rr")
        return jsonify(data), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Fallo al conectar con {target}", "detalles": str(e)}), 502


# ---------------------------------------------------------------------------
# Least Connections (segundo baseline)
# ---------------------------------------------------------------------------
@app.route("/api/lc/student/record", methods=["GET", "POST"])
def proxy_least_connections():
    with lc_lock:
        least = min(lc_active.values())
        # desempate aleatorio: sin esto, con tráfico bajo siempre ganaba la primera
        target = random.choice([i for i, c in lc_active.items() if c == least])
        lc_active[target] += 1
    try:
        resp = forward_to_user(target)
        data = resp.json()
        data.update(load_balancer="Least-Connections", handled_by_instance=target)
        count(target, "lc")
        return jsonify(data), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Fallo al conectar con {target}", "detalles": str(e)}), 502
    finally:
        with lc_lock:
            lc_active[target] = max(0, lc_active[target] - 1)


# ---------------------------------------------------------------------------
# GNN + RL
# ---------------------------------------------------------------------------
@app.route("/api/gnn/student/record", methods=["GET", "POST"])
def proxy_gnn_intelligent():
    target, ctx = gnn_env.select_action()  # suma 1 conexión activa al elegido
    start = time.perf_counter()
    ok = False
    try:
        resp = forward_to_user(target)
        ok = resp.status_code == 200
        try:
            data = resp.json()
        except ValueError:                      # la réplica no devolvió JSON
            data = {"raw": resp.text[:200]}
        data.update(load_balancer="GNN-RL-Intelligent", handled_by_instance=target)
        if ok:
            count(target, "gnn")
        out = (jsonify(data), resp.status_code)
    except Exception as e:
        out = (jsonify({"error": f"Fallo al conectar con {target}", "detalles": str(e)}), 502)
    finally:
        # se ejecuta UNA sola vez, pase lo que pase
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        gnn_env.on_complete(target, elapsed_ms, ok)
        gnn_env.learn(ctx, gnn_env.compute_reward(elapsed_ms, ok))
    return out


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)