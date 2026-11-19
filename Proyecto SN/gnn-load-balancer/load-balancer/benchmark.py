"""
Benchmark P1: Round Robin vs Least Connections vs GNN+RL.

Diseño experimental
-------------------
* 3 escenarios: carga baja, carga alta y réplica congestionada.
* La congestión de user-svc-2 se activa SOLO en el escenario 3 (POST /admin/congestion).
* Cada escenario hace un warm-up (no medido) con los 3 algoritmos y luego
  REPS repeticiones. El orden de los algoritmos se baraja en cada repetición.
* Se miden: latencia P95 (solo éxitos), throughput, tasa de errores,
  CPU/RAM por réplica (muestreo de /metrics durante la corrida) y reparto
  de peticiones por réplica.
* Se guardan datos crudos (requests.csv, resources.csv), resumen por corrida
  (runs.csv), resumen agregado (summary.csv) y gráficas con barras de error.

Uso:
    python benchmark.py                 # experimento completo
    python benchmark.py --quick         # prueba rápida (2 reps, menos peticiones)
    python benchmark.py --reps 10 --seed 7
"""
import argparse
import csv
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests

LB_URL = os.getenv("LB_URL", "http://localhost:8080")
REPLICAS = {                       # nombre -> URL publicada en el host (docker-compose)
    "user-svc-1": os.getenv("REPLICA1_URL", "http://localhost:5011"),
    "user-svc-2": os.getenv("REPLICA2_URL", "http://localhost:5012"),
}
CONGESTED_REPLICA = "user-svc-2"
CONGESTION = {"enabled": True, "delay_ms": 400, "cpu_ms": 30}

ALGOS = {"Round Robin": "rr", "Least Connections": "lc", "GNN-RL": "gnn"}
COLORS = {"Round Robin": "#ff7f0e", "Least Connections": "#1f77b4", "GNN-RL": "#2ca02c"}

SCENARIOS = [
    # nombre, peticiones, workers concurrentes, congestión activa
    ("1. Carga baja", 200, 5, False),
    ("2. Carga alta", 800, 40, False),
    ("3. Congestionado", 400, 20, True),
]

_tls = threading.local()


def session():
    if not hasattr(_tls, "s"):
        _tls.s = requests.Session()
    return _tls.s


# ---------------------------------------------------------------------------
# Utilidades de control
# ---------------------------------------------------------------------------
def set_congestion(enabled):
    body = dict(CONGESTION, enabled=enabled)
    requests.post(REPLICAS[CONGESTED_REPLICA] + "/admin/congestion", json=body, timeout=5)


def wait_ready(timeout=60):
    t0 = time.time()
    urls = [LB_URL + "/health"] + [u + "/health" for u in REPLICAS.values()]
    while time.time() - t0 < timeout:
        try:
            if all(requests.get(u, timeout=2).status_code == 200 for u in urls):
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Los servicios no están listos. ¿docker compose up -d?")


def one_request(url):
    t0 = time.perf_counter()
    try:
        r = session().get(url, timeout=5)
        lat = (time.perf_counter() - t0) * 1000.0
        inst = ""
        if r.status_code == 200:
            inst = r.json().get("replica", "")
        return {"t": t0, "lat": lat, "ok": r.status_code == 200,
                "status": r.status_code, "replica": inst}
    except Exception:
        return {"t": t0, "lat": (time.perf_counter() - t0) * 1000.0, "ok": False,
                "status": 0, "replica": ""}


class ResourceSampler(threading.Thread):
    """Muestrea /metrics de cada réplica mientras corre una prueba."""

    def __init__(self, period=0.5):
        super().__init__(daemon=True)
        self.period, self.samples, self._halt = period, [], threading.Event()

    def run(self):
        while not self._halt.is_set():
            for name, url in REPLICAS.items():
                try:
                    m = requests.get(url + "/metrics", timeout=1).json()
                    self.samples.append((time.time(), name, m["cpu_percent"], m["mem_mb"]))
                except Exception:
                    pass
            time.sleep(self.period)

    def stop(self):
        self._halt.set()
        self.join(timeout=3)


def run_load(algo_key, n_requests, workers):
    url = f"{LB_URL}/api/{algo_key}/student/record"
    sampler = ResourceSampler()
    sampler.start()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda _: one_request(url), range(n_requests)))
    wall = time.perf_counter() - t0
    sampler.stop()
    return results, wall, sampler.samples


# ---------------------------------------------------------------------------
# Experimento
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    scenarios = SCENARIOS
    if args.quick:
        args.reps, args.warmup = 2, 60
        scenarios = [(n, max(40, r // 5), w, c) for n, r, w, c in SCENARIOS]

    random.seed(args.seed)
    out_dir = os.path.join("results", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    print("=== BENCHMARK P1: Round Robin vs Least Connections vs GNN-RL ===")
    print(f"Repeticiones: {args.reps} | warm-up: {args.warmup} | semilla: {args.seed}")
    wait_ready()

    req_rows, res_rows, run_rows = [], [], []
    requests.post(LB_URL + "/api/gnn/reset", timeout=5)   # una sola vez, al inicio

    try:
        for sc_name, n_req, workers, congested in scenarios:
            print(f"\n--- {sc_name} | {n_req} req, {workers} workers, congestión={congested} ---")
            set_congestion(congested)
            time.sleep(1)

            # Warm-up (no medido) para todos los algoritmos: el GNN aprende el
            # estado del escenario y los demás calientan sus conexiones.
            for algo_key in ALGOS.values():
                run_load(algo_key, args.warmup, workers)

            for rep in range(1, args.reps + 1):
                order = list(ALGOS.items())
                random.shuffle(order)
                for algo_name, algo_key in order:
                    results, wall, samples = run_load(algo_key, n_req, workers)

                    oks = [r["lat"] for r in results if r["ok"]]
                    n_err = len(results) - len(oks)
                    p95 = float(np.percentile(oks, 95)) if oks else float("nan")
                    p50 = float(np.percentile(oks, 50)) if oks else float("nan")
                    thr = len(oks) / wall if wall > 0 else 0.0
                    err = 100.0 * n_err / len(results)
                    share2 = 100.0 * sum(r["replica"] == CONGESTED_REPLICA for r in results) \
                        / max(1, len(oks))

                    cpu = {n: [s[2] for s in samples if s[1] == n] for n in REPLICAS}
                    mem = {n: [s[3] for s in samples if s[1] == n] for n in REPLICAS}
                    cpu_mean = float(np.mean([np.mean(v) for v in cpu.values() if v] or [0]))
                    mem_mean = float(np.mean([np.mean(v) for v in mem.values() if v] or [0]))

                    run_rows.append({
                        "scenario": sc_name, "rep": rep, "algo": algo_name,
                        "p50_ms": p50, "p95_ms": p95, "throughput_rps": thr,
                        "error_rate_pct": err, "cpu_mean_pct": cpu_mean,
                        "mem_mean_mb": mem_mean, "share_congested_pct": share2,
                        "n_requests": len(results), "wall_s": wall,
                    })
                    for r in results:
                        req_rows.append({"scenario": sc_name, "rep": rep, "algo": algo_name,
                                         "t": round(r["t"], 4), "latency_ms": round(r["lat"], 2),
                                         "ok": int(r["ok"]), "status": r["status"],
                                         "replica": r["replica"]})
                    for ts, name, c, m in samples:
                        res_rows.append({"scenario": sc_name, "rep": rep, "algo": algo_name,
                                         "ts": round(ts, 3), "replica": name,
                                         "cpu_percent": c, "mem_mb": m})

                    print(f"  rep {rep} [{algo_name:17}] P95 {p95:7.1f} ms | "
                          f"{thr:6.1f} req/s | err {err:4.1f}% | "
                          f"→{CONGESTED_REPLICA}: {share2:4.1f}%")
                    time.sleep(1)
    finally:
        set_congestion(False)   # deja el sistema sano pase lo que pase

    write_csv(os.path.join(out_dir, "requests.csv"), req_rows)
    write_csv(os.path.join(out_dir, "resources.csv"), res_rows)
    write_csv(os.path.join(out_dir, "runs.csv"), run_rows)
    summary = summarize(run_rows)
    write_csv(os.path.join(out_dir, "summary.csv"), summary)
    plot(summary, [s[0] for s in scenarios], out_dir)
    print_table(summary)
    print(f"\n[OK] Resultados guardados en: {out_dir}")


# ---------------------------------------------------------------------------
# Resumen, tablas y gráficas
# ---------------------------------------------------------------------------
METRICS = ["p95_ms", "p50_ms", "throughput_rps", "error_rate_pct",
           "cpu_mean_pct", "mem_mean_mb", "share_congested_pct"]


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarize(run_rows):
    out = []
    keys = sorted({(r["scenario"], r["algo"]) for r in run_rows})
    for sc, algo in keys:
        rs = [r for r in run_rows if r["scenario"] == sc and r["algo"] == algo]
        row = {"scenario": sc, "algo": algo, "n_reps": len(rs)}
        for m in METRICS:
            v = np.array([r[m] for r in rs], dtype=float)
            row[m + "_mean"] = float(np.nanmean(v))
            row[m + "_std"] = float(np.nanstd(v, ddof=1)) if len(v) > 1 else 0.0
        out.append(row)
    return out


def print_table(summary):
    print("\n=========== RESUMEN (media ± desviación entre repeticiones) ===========")
    print(f"{'Escenario':20}{'Algoritmo':19}{'P95 (ms)':>16}{'Req/s':>16}{'Err %':>12}{'→réplica lenta %':>20}")
    for r in summary:
        print(f"{r['scenario']:20}{r['algo']:19}"
              f"{r['p95_ms_mean']:9.1f}±{r['p95_ms_std']:5.1f}"
              f"{r['throughput_rps_mean']:9.1f}±{r['throughput_rps_std']:5.1f}"
              f"{r['error_rate_pct_mean']:7.2f}±{r['error_rate_pct_std']:4.2f}"
              f"{r['share_congested_pct_mean']:12.1f}±{r['share_congested_pct_std']:4.1f}")


def plot(summary, scenario_names, out_dir):
    panels = [
        ("p95_ms", "Latencia P95 (ms) ↓"),
        ("throughput_rps", "Throughput (req/s) ↑"),
        ("error_rate_pct", "Tasa de errores (%) ↓"),
        ("cpu_mean_pct", "CPU media de réplicas (% de 1 núcleo)"),
        ("mem_mean_mb", "RAM media de réplicas (MB)"),
        ("share_congested_pct", f"% de peticiones a {CONGESTED_REPLICA}"),
    ]
    x = np.arange(len(scenario_names))
    width = 0.26
    fig, axs = plt.subplots(2, 3, figsize=(18, 9))
    fig.suptitle("Round Robin vs Least Connections vs GNN-RL (media ± desv. estándar)",
                 fontsize=14, fontweight="bold")
    for ax, (key, title) in zip(axs.ravel(), panels):
        for i, algo in enumerate(ALGOS):
            means, stds = [], []
            for sc in scenario_names:
                r = next((s for s in summary if s["scenario"] == sc and s["algo"] == algo), None)
                means.append(r[key + "_mean"] if r else 0)
                stds.append(r[key + "_std"] if r else 0)
            ax.bar(x + (i - 1) * width, means, width, yerr=stds, capsize=3,
                   label=algo, color=COLORS[algo], alpha=0.9)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(scenario_names, fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "benchmark_resultados.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()