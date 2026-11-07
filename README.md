# GNN Intelligent Load Balancer - SGA ESPOL

Sistema de balanceo de carga inteligente basado en **Graph Neural Networks (GNN)** y **Aprendizaje por Refuerzo (RL)** diseñado para optimizar el enrutamiento de tráfico en una arquitectura de microservicios inspirada en el Sistema de Gestión Académica (SGA) de la ESPOL.

El proyecto permite comparar cuantitativamente el desempeño de enrutadores tradicionales (*Round Robin* y *Least Connections*) frente a un agente inteligente que evalúa dinámicamente el estado de la red y el rendimiento de los microservicios.

---

## 🏛️ Arquitectura del Sistema

La infraestructura está completamente containerizada mediante **Docker Compose** y consta de 5 microservicios independientes:

1. **`load-balancer` (Puerto 8080):** Núcleo en Flask que aloja las interfaces web (`/` y `/dashboard`), ejecuta los algoritmos de balanceo (Round Robin, Least Connections y GNN-RL) y expone la API de métricas en tiempo real (`/api/metrics`).
2. **`user-svc-1` (Puerto interno 5000):** Réplica 1 del microservicio de consulta de récord académico y datos de estudiantes.
3. **`user-svc-2` (Puerto interno 5000):** Réplica 2 del microservicio de usuarios.
4. **`auth-svc` (Puerto interno 5001):** Microservicio para autenticación e inicio de sesión en el SGA.
5. **`course-svc` (Puerto interno 5003):** Microservicio para inscripción de materias y oferta académica.

### Diagrama de Red de Microservicios

```mermaid
graph TD
    %% Capa de Cliente e Interfaz
    Client["Navegador / Usuario<br>SGA Portal & Dashboard"] -->|HTTP / Puerto 8080| LB["load-balancer<br>(Flask Proxy + GNN-RL Engine)"]

    %% Red Docker y Microservicios
    subgraph Docker_Network ["Red Docker Compose (Microservicios)"]
        LB -->|"/api/sga/login"| Auth["auth-svc<br>(Puerto 5001)"]
        LB -->|"/api/courses/enroll"| Course["course-svc<br>(Puerto 5003)"]
        
        subgraph User_Pool ["Pool de Réplicas (Balanceo de Carga)"]
            LB -->|"Round Robin / Least Connections / GNN-RL"| User1["user-svc-1<br>(Puerto 5000)"]
            LB -->|"Round Robin / Least Connections / GNN-RL"| User2["user-svc-2<br>(Puerto 5000)"]
        end
    end

    style LB fill:#38bdf8,stroke:#0369a1,stroke-width:2px,color:#000
    style User1 fill:#34d399,stroke:#047857,stroke-width:2px,color:#000
    style User2 fill:#34d399,stroke:#047857,stroke-width:2px,color:#000
    style Auth fill:#fbbf24,stroke:#b45309,stroke-width:2px,color:#000
    style Course fill:#fbbf24,stroke:#b45309,stroke-width:2px,color:#000
🚀 Algoritmos de Balanceo Implementados
Round Robin (/api/rr/student/record): Asigna peticiones de forma cíclica y secuencial a los nodos disponibles.

Least Connections (/api/lc/student/record): Evalúa cuál instancia posee el menor número de conexiones activas en el instante de la solicitud.

GNN-RL Inteligente (/api/gnn/student/record): Agente de Aprendizaje por Refuerzo basado en el estado del grafo de la red (IntelligentLoadBalancerEnv). Toma decisiones de enrutamiento considerando la latencia histórica, saturación y penalizaciones por tiempo de respuesta.

🛠️ Requisitos Previos
Docker y Docker Compose

Python 3.9+ (opcional, para ejecutar el script de benchmark localmente)

📦 Instalación y Despliegue
Clonar el repositorio:

Bash
git clone [https://github.com/TU_USUARIO/gnn-load-balancer.git](https://github.com/TU_USUARIO/gnn-load-balancer.git)
cd gnn-load-balancer
Levantar los microservicios con Docker Compose:

Bash
docker compose build --no-cache
docker compose up -d
Verificar el estado de los contenedores:

Bash
docker compose ps
💻 Uso e Interfaces Web
Una vez levantados los contenedores, accede a través del navegador:

Portal de Simulación SGA: http://localhost:8080/

Permite simular interacciones de estudiantes y generar peticiones hacia el balanceador para cada algoritmo.

Dashboard de Monitoreo en Tiempo Real (DevOps): http://localhost:8080/dashboard

Visualiza en tarjetas dinámicas las conexiones activas, peticiones acumuladas y estado de salud de cada microservicio (user-svc-1 y user-svc-2).

📊 Pruebas Experimentales y Benchmark
El proyecto incluye un script de benchmarking concurrente (benchmark.py) que ejecuta ráfagas de peticiones sobre los tres algoritmos, mide la latencia promedio y el throughput (peticiones por segundo), y genera automáticamente una gráfica comparativa.

Ejecución del Benchmark:
Instalar dependencias en Python:

Bash
pip install requests matplotlib numpy
Ejecutar la suite de pruebas:

Bash
python benchmark.py
El script generará el archivo benchmark_results.png en el directorio raíz, comparando:

Latencia Promedio (ms) (Menor es mejor)

Throughput (req/s) (Mayor es mejor)

📈 Métricas Recolectadas
El sistema recopila y expone en /api/metrics:

Conexiones activas por nodo.

Peticiones totales atendidas por nodo.

Latencia de respuesta individual y promedio (ms).

Recompensa (Reward) obtenida por el agente RL.

👥 Integrantes
Guillermo Mero - Telempática / FIEC / ESPOL
Saúl Quiroz - Telemática /FIEC / ESPOL