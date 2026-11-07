import time
import requests
import concurrent.futures
import matplotlib.pyplot as plt
import numpy as np

# Configuración de Endpoints
BASE_URL = "http://localhost:8080/api"
ENDPOINTS = {
    "Round Robin": f"{BASE_URL}/rr/student/record",
    "Least Connections": f"{BASE_URL}/lc/student/record",
    "GNN-RL Inteligente": f"{BASE_URL}/gnn/student/record"
}

NUM_REQUESTS = 120  # Peticiones totales por algoritmo
CONCURRENCY = 12    # Peticiones en paralelo

def make_request(url):
    """Envia una petición y calcula la latencia en ms."""
    start = time.time()
    try:
        response = requests.post(
            url, 
            json={"student_id": "202112345", "action": "benchmark"}, 
            timeout=5
        )
        latency = (time.time() - start) * 1000
        success = response.status_code == 200
        return latency, success
    except Exception:
        return (time.time() - start) * 1000, False

def run_benchmark(name, url):
    """Ejecuta ráfagas concurrentes y calcula métricas."""
    print(f"🚀 Iniciando prueba para: {name} ({NUM_REQUESTS} peticiones)...")
    latencies = []
    successes = 0

    start_total = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(make_request, url) for _ in range(NUM_REQUESTS)]
        for future in concurrent.futures.as_completed(futures):
            lat, ok = future.result()
            latencies.append(lat)
            if ok:
                successes += 1
    
    total_time = time.time() - start_total
    throughput = successes / total_time
    avg_latency = np.mean(latencies)

    print(f"   ✅ Latencia Promedio: {avg_latency:.2f} ms")
    print(f"   ✅ Throughput: {throughput:.2f} req/sec\n")
    
    return latencies, avg_latency, throughput

def generate_charts(results):
    """Genera y guarda la gráfica comparativa de 3 métodos para las diapositivas."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Comparación Experimental: Baselines vs. GNN-RL', fontsize=15, fontweight='bold')

    algorithms = list(results.keys())
    avg_latencies = [results[alg]['avg_latency'] for alg in algorithms]
    throughputs = [results[alg]['throughput'] for alg in algorithms]

    # Colores distintos para los 3 métodos (Round Robin, Least Connections, GNN-RL)
    colors = ['#38bdf8', '#fbbf24', '#34d399']

    # 1. Gráfica de Latencia Promedio
    bars1 = ax1.bar(algorithms, avg_latencies, color=colors, width=0.55)
    ax1.set_title('Latencia Promedio (Menor es mejor)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Latencia (ms)')
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 1, f"{yval:.2f} ms", ha='center', va='bottom', fontweight='bold', fontsize=9)

    # 2. Gráfica de Throughput
    bars2 = ax2.bar(algorithms, throughputs, color=colors, width=0.55)
    ax2.set_title('Throughput (Mayor es mejor)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Peticiones / Segundo (req/s)')
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.2f} req/s", ha='center', va='bottom', fontweight='bold', fontsize=9)

    plt.tight_layout()
    plt.savefig('benchmark_results.png', dpi=300)
    print("📊 ¡Gráfica de 3 métodos guardada exitosamente como 'benchmark_results.png'!")

if __name__ == "__main__":
    results = {}
    for name, url in ENDPOINTS.items():
        latencies, avg_lat, thp = run_benchmark(name, url)
        results[name] = {
            'latencies': latencies,
            'avg_latency': avg_lat,
            'throughput': thp
        }
    
    generate_charts(results)