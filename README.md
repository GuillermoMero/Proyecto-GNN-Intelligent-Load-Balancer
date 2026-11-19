# GNN Intelligent Load Balancer - SGA ESPOL

Sistema de balanceo de carga inteligente basado en **Graph Neural Networks (GNN)** y **Aprendizaje por Refuerzo (RL)** para enrutar tráfico en una arquitectura de microservicios inspirada en el Sistema de Gestión Académica (SGA) de la ESPOL.

El proyecto compara cuantitativamente dos balanceadores tradicionales (**Round Robin** y **Least Connections**) frente a un agente **GNN + RL** que representa los microservicios como un grafo de dependencias y usa el estado global del sistema para decidir a qué réplica enviar cada petición.


---

## 🏛️ Arquitectura del Sistema

La infraestructura está completamente containerizada mediante **Docker Compose** y consta de 5 microservicios independientes.
<img width="2800" height="1640" alt="arquitectura" src="https://github.com/user-attachments/assets/61696c0a-a234-40c1-92ef-ac29e87540e6" />

# 🚀 Algoritmos de Balanceo

Los tres algoritmos balancean el mismo servicio replicado (`user-svc`) y reenvían al mismo endpoint, así que la única diferencia entre ellos es la decisión de destino.

- **Round Robin** (`/api/rr/student/record`): asigna las peticiones de forma cíclica. Baseline obligatorio.
- **Least Connections** (`/api/lc/student/record`): elige la réplica con menos conexiones activas, con desempate aleatorio.
- **GNN + RL** (`/api/gnn/student/record`):
  - **Grafo de dependencias:** 6 nodos (`gateway`, `auth-svc`, `course-svc`, `redis`, `user-svc-1`, `user-svc-2`) y 7 aristas, que son las dependencias reales del `docker-compose` más una arista entre réplicas.
  - **Features por nodo:** conexiones activas, latencia EMA, CPU %, RAM MB e indicador de réplica. Se actualizan por polling cada 1 s; la latencia de Redis la mide `auth-svc` con `PING`.
  - **GNN:** 2 capas tipo GraphSAGE implementadas en NumPy. Cada réplica recibe información de hasta 2 saltos del grafo y la red produce un valor Q por nodo.
  - **Política:** softmax con temperatura (τ = 0.3) más exploración ε (0.10 → 0.02), aplicada solo sobre las réplicas (máscara de acciones).
  - **Aprendizaje:** Q-learning en línea con γ = 0 (bandido contextual); los pesos se actualizan después de cada petición.
  - **Reward:** `−latencia/100 − λ · cola_al_elegir`, con λ = 0.1 (configurable con `GNN_CONGESTION_LAMBDA`). El término de cola evita saturar la réplica sana.
  - **Estado obsoleto:** si una réplica pasa más de 5 s sin tráfico, su latencia EMA decae un 5 % por segundo para volver a probarla.

## 🛠️ Requisitos Previos

- Docker y Docker Compose
- Python 3.9+ (para ejecutar el benchmark)

## 📦 Instalación y Despliegue

Clonar el repositorio:

```bash
git clone https://github.com/TU_USUARIO/gnn-load-balancer.git
cd gnn-load-balancer
```

Levantar los servicios:

```bash
docker compose build --no-cache
docker compose up -d
```

Verificar el estado de los contenedores:

```bash
docker compose ps
```

## 💻 Interfaces Web

- **Portal de simulación SGA:** http://localhost:8080/
  Envía peticiones individuales a cada algoritmo y a los servicios de login y matrícula.
- **Dashboard de monitoreo:** http://localhost:8080/dashboard
  Muestra las conexiones activas y las peticiones atendidas por cada réplica en tiempo real.

## 🔌 API

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/{rr,lc,gnn}/student/record` | GET/POST | Consulta de récord balanceada con cada algoritmo |
| `/api/sga/login` | POST | Login (proxy a `auth-svc`) |
| `/api/courses/enroll` | POST | Matrícula (proxy a `course-svc`) |
| `/api/metrics` | GET | Datos para el dashboard |
| `/api/gnn/state` | GET | Estado completo del grafo: nodos, aristas, features, Q-values, ε y reward medio |
| `/api/gnn/reset` | POST | Reinicia el aprendizaje del agente |
| `/api/stats` | GET/DELETE | Peticiones por réplica y algoritmo (DELETE las pone en 0) |

## 📊 Benchmark

`benchmark.py` compara los tres algoritmos en 3 escenarios, con 5 repeticiones cada uno en orden aleatorio (semilla 42) y un calentamiento no medido antes de cada escenario.

| Escenario | Peticiones | Clientes concurrentes | Condición |
|---|---|---|---|
| 1. Carga baja | 200 | 5 | Réplicas sanas |
| 2. Carga alta | 800 | 40 | Réplicas sanas |
| 3. Congestionado | 400 | 20 | `user-svc-2` con +400 ms de espera y +30 ms de CPU por petición |

Instalar dependencias y ejecutar:

```bash
pip install requests numpy matplotlib
cd load-balancer
python benchmark.py                 # experimento completo
python benchmark.py --quick         # prueba rápida
python benchmark.py --warmup 400    # calentamiento más largo
```

**Métricas medidas:** latencia P95 y P50 (solo peticiones exitosas), throughput, tasa de errores, CPU y RAM de las réplicas, y porcentaje de peticiones enviadas a la réplica congestionada.

**Archivos generados** en `results/<fecha>/`:

- `requests.csv`: cada petición individual (latencia, estado, réplica)
- `resources.csv`: muestras de CPU y RAM de cada réplica
- `runs.csv`: métricas por corrida
- `summary.csv`: media ± desviación estándar por escenario y algoritmo
- `benchmark_resultados.png`: gráficas comparativas con barras de error

## 📈 Resultados Preliminares

Media ± desviación estándar de 5 repeticiones (resultados en `results/20261119_000632/`).

| Escenario | Algoritmo | P95 (ms) | Throughput (req/s) | % a réplica lenta |
|---|---|---|---|---|
| 1. Carga baja | Round Robin | 97 ± 14 | 84.6 | 50.0 |
| | Least Connections | 120 ± 24 | 73.8 | 49.6 |
| | GNN-RL | 106 ± 20 | 75.3 | 52.6 |
| 2. Carga alta | Round Robin | 821 ± 295 | 74.7 | 50.0 |
| | Least Connections | 737 ± 114 | 79.1 | 49.5 |
| | GNN-RL | 855 ± 140 | 72.1 | 49.9 |
| 3. Congestionado | Round Robin | 977 ± 72 | 46.6 | 50.0 |
| | Least Connections | 669 ± 22 | 69.5 | 14.3 |
| | GNN-RL | **632 ± 60** | 67.9 | **9.3** |

No hubo errores en ninguna corrida.

**Lectura:**

- Con réplicas sanas (escenarios 1 y 2), los tres algoritmos empatan dentro de la desviación estándar: repartir 50/50 ya es lo óptimo.
- Con una réplica congestionada, GNN-RL obtiene la menor latencia P95: −35 % frente a Round Robin y −6 % frente a Least Connections, con un throughput similar al de LC. Es el algoritmo que más evita la réplica lenta.
- El aprendizaje se ve entre repeticiones: el porcentaje enviado a la réplica lenta baja de 17 % a 4.5 %.

La ventaja frente a Least Connections es pequeña y está dentro de la desviación estándar, así que se considera **evidencia preliminar**.

## ⚠️ Limitaciones (a abordar en el Segundo Parcial)

- La congestión es simulada: un retraso fijo más CPU consumida.
- Solo una réplica congestionada y siempre la misma.
- Grafo pequeño (6 nodos).
- Reward fijo y sin horizonte temporal (γ = 0).
- Sin mecanismo de atención propio.
- Todo corre en una sola máquina, así que la carga de la PC introduce ruido en las mediciones.

## 👥 Integrantes

- Guillermo Mero - Telemática / FIEC / ESPOL
- Saul Quiroz - Telemática / FIEC / ESPOL

Latencia de respuesta individual y promedio (ms).

Recompensa (Reward) obtenida por el agente RL.

👥 Integrantes
Guillermo Mero - Telemática / FIEC / ESPOL
Saul Quiroz - Telemática / FIEC / ESPOL
