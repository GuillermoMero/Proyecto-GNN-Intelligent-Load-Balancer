from flask import Flask, jsonify, request
import os
import time
import threading
import psutil

app = Flask(__name__)

REPLICA_ID = os.getenv("REPLICA_ID", "unknown")

# ---------------------------------------------------------------------------
# Configuración de congestión (modificable en caliente vía /admin/congestion)
#   delay_ms : retraso fijo por petición (simula espera de I/O)
#   cpu_ms   : milisegundos de CPU ocupada por petición (consume CPU real)
# ---------------------------------------------------------------------------
_cfg_lock = threading.Lock()
_congestion = {
    "enabled": os.getenv("SIMULATE_CONGESTION", "false").lower() == "true",
    "delay_ms": int(os.getenv("CONGESTION_DELAY_MS", "400")),
    "cpu_ms": int(os.getenv("CONGESTION_CPU_MS", "30")),
}

# ---------------------------------------------------------------------------
# Estado interno para /metrics
# ---------------------------------------------------------------------------
_stats_lock = threading.Lock()
_active = 0
_total = 0
_errors = 0
_avg_latency_ms = 0.0  # EMA de la latencia de servicio
_process = psutil.Process(os.getpid())
_process.cpu_percent(interval=None)  # primera llamada de calibración


def _burn_cpu(ms):
    """Mantiene la CPU ocupada ~ms milisegundos (consumo real, no sleep)."""
    end = time.perf_counter() + ms / 1000.0
    x = 0
    while time.perf_counter() < end:
        x += 1
    return x


@app.route("/student/record", methods=["GET", "POST"])
def student_record():
    global _active, _total, _avg_latency_ms
    start = time.perf_counter()

    with _stats_lock:
        _active += 1

    try:
        with _cfg_lock:
            cfg = dict(_congestion)

        if cfg["enabled"]:
            if cfg["cpu_ms"] > 0:
                _burn_cpu(cfg["cpu_ms"])
            if cfg["delay_ms"] > 0:
                time.sleep(cfg["delay_ms"] / 1000.0)

        return jsonify({
            "status": "success",
            "replica": REPLICA_ID,
            "message": "Historial académico consultado con éxito",
        })
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        with _stats_lock:
            _active -= 1
            _total += 1
            if _avg_latency_ms == 0.0:
                _avg_latency_ms = elapsed
            else:
                _avg_latency_ms = _avg_latency_ms * 0.8 + elapsed * 0.2


@app.route("/admin/congestion", methods=["GET", "POST"])
def admin_congestion():
    """
    GET  -> devuelve la configuración actual.
    POST -> {"enabled": true, "delay_ms": 400, "cpu_ms": 30}
            Todos los campos son opcionales.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        with _cfg_lock:
            if "enabled" in data:
                _congestion["enabled"] = bool(data["enabled"])
            if "delay_ms" in data:
                _congestion["delay_ms"] = max(0, int(data["delay_ms"]))
            if "cpu_ms" in data:
                _congestion["cpu_ms"] = max(0, int(data["cpu_ms"]))
    with _cfg_lock:
        return jsonify({"replica": REPLICA_ID, **_congestion})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "replica": REPLICA_ID}), 200


@app.route("/metrics", methods=["GET"])
def metrics():
    """Estado de la réplica: es la entrada de datos para el balanceador."""
    with _stats_lock:
        snap = {
            "replica": REPLICA_ID,
            "active_connections": _active,
            "total_requests": _total,
            "avg_latency_ms": round(_avg_latency_ms, 2),
        }
    # CPU del proceso (100 = un núcleo completo) y RAM residente en MB
    snap["cpu_percent"] = _process.cpu_percent(interval=None)
    snap["mem_mb"] = round(_process.memory_info().rss / (1024 * 1024), 2)
    with _cfg_lock:
        snap["congestion"] = dict(_congestion)
    return jsonify(snap)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)