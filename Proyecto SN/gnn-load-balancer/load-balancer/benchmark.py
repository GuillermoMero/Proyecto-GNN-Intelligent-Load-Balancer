import time
import subprocess
import concurrent.futures
import requests
import numpy as np
import matplotlib.pyplot as plt

BASE_URL = "http://localhost:8080"

# Endpoints activos mapeados en el balanceador para la evaluación
SERVICES_ROUTES = {
    "Consulta Académica / Récord": "/api/{mode}/student/record"
}

ALGOS = {
    "Round Robin": "rr",
    "Least Connections": "lc",
    "GNN-RL (IA)": "gnn"
}

def get_docker_cpu():
    """Captura el porcentaje promedio de CPU de los contenedores del clúster."""
    try:
        cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}}:{{.CPUPerc}}"]
        output = subprocess.check_output(cmd, text=True)
        cpus = []
        for line in output.strip().split("\n"):
            if any(k in line for k in ["user-svc", "load-balancer"]):
                val = float(line.split(":")[1].replace("%", "").strip())
                cpus.append(val)
        return round(np.mean(cpus), 2) if cpus else 0.0
    except Exception:
        return 0.0

def send_request(url):
    start_time = time.time()
    try:
        response = requests.get(url, timeout=5)
        duration = (time.time() - start_time) * 1000
        return duration, (response.status_code == 200)
    except Exception:
        return 0, False

def run_load_test(url, num_requests, max_workers):
    latencies = []
    errors = 0
    cpu_samples = []
    start_wall = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(send_request, url) for _ in range(num_requests)]
        
        # Muestreo de CPU durante la ráfaga de tráfico
        time.sleep(0.3)
        cpu_samples.append(get_docker_cpu())
        
        for future in concurrent.futures.as_completed(futures):
            duration, success = future.result()
            if success:
                latencies.append(duration)
            else:
                errors += 1
                
    total_time = time.time() - start_wall
    throughput = num_requests / total_time if total_time > 0 else 0
    p95_latency = np.percentile(latencies, 95) if latencies else 0
    error_rate = (errors / num_requests) * 100 if num_requests > 0 else 0
    avg_cpu = np.mean(cpu_samples) if cpu_samples else 0
    
    return p95_latency, throughput, error_rate, avg_cpu

def main():
    scenarios = {
        "1. Carga Baja": {"requests": 50, "workers": 5},
        "2. Carga Alta": {"requests": 300, "workers": 30},
        "3. Congestionado": {"requests": 150, "workers": 20}
    }
    
    results = {algo: {"p95": [], "tp": [], "err": [], "cpu": []} for algo in ALGOS}
    
    print("=== INICIANDO BENCHMARK ESTABLE (TCG_GUARDIAN S.A.) ===")
    
    for scenario_name, params in scenarios.items():
        print(f"\n--- Escenario: {scenario_name} ---")
        for algo_name, mode in ALGOS.items():
            
            total_p95, total_tp, total_err, total_cpu = [], [], [], []
            
            for service_name, route_template in SERVICES_ROUTES.items():
                url = f"{BASE_URL}{route_template.format(mode=mode)}"
                p95, tp, err, cpu = run_load_test(url, params["requests"], params["workers"])
                total_p95.append(p95)
                total_tp.append(tp)
                total_err.append(err)
                total_cpu.append(cpu)
            
            avg_p95 = np.mean(total_p95)
            avg_tp = np.mean(total_tp)
            avg_err = np.mean(total_err)
            avg_cpu = np.mean(total_cpu)
            
            results[algo_name]["p95"].append(avg_p95)
            results[algo_name]["tp"].append(avg_tp)
            results[algo_name]["err"].append(avg_err)
            results[algo_name]["cpu"].append(avg_cpu)
            
            print(f"[{algo_name:17}] P95: {avg_p95:5.1f} ms | TP: {avg_tp:5.1f} req/s | Err: {avg_err:4.1f}% | CPU: {avg_cpu:5.1f}%")

    # Generación de la Gráfica 2x2
    x = np.arange(len(scenarios))
    width = 0.25
    colors = ['#ff7f0e', '#1f77b4', '#2ca02c']
    
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Evaluación Experimental de Desempeño: GNN-RL vs Baselines", fontsize=14, fontweight='bold')
    
    metrics_config = [
        (axs[0, 0], "p95", "Latencia P95 (ms) [Menor es mejor]", "Latencia P95 por Escenario"),
        (axs[0, 1], "tp",  "Throughput (req/s) [Mayor es mejor]", "Rendimiento (Throughput)"),
        (axs[1, 0], "err", "Tasa de Errores (%) [Menor es mejor]", "Tasa de Errores HTTP"),
        (axs[1, 1], "cpu", "Utilización Promedio CPU (%)", "Utilización de Recursos (CPU)")
    ]
    
    for ax, key, ylabel, title in metrics_config:
        for i, ((algo_name, data), color) in enumerate(zip(results.items(), colors)):
            offset = (i - 1) * width
            ax.bar(x + offset, data[key], width, label=algo_name, color=color, alpha=0.85)
        ax.set_ylabel(ylabel, fontweight='bold')
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(list(scenarios.keys()))
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.savefig("benchmark_resultados_finales.png", dpi=300)
    print("\n[✔] Gráfica guardada exitosamente como 'benchmark_resultados_finales.png'")
    plt.show()

if __name__ == "__main__":
    main()