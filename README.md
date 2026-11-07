# GNN Intelligent Load Balancer - SGA ESPOL

Sistema de balanceo de carga inteligente basado en **Graph Neural Networks (GNN)** y **Aprendizaje por Refuerzo (RL)** diseñado para optimizar el enrutamiento de tráfico en una arquitectura de microservicios inspirada en el Sistema de Gestión Académica (SGA) de la ESPOL.

El proyecto permite comparar cuantitativamente el desempeño de enrutadores tradicionales (*Round Robin* y *Least Connections*) frente a un agente inteligente que evalúa dinámicamente el estado de la red y el rendimiento de los microservicios.

---

## 🏛️ Arquitectura del Sistema

La infraestructura está completamente containerizada mediante **Docker Compose** y consta de 5 microservicios independientes.

![Arquitectura del Sistema](Arquitectura.jfif)

### Componentes Principales:
1. **`load-balancer` (Puerto 8080):** Núcleo en Flask que aloja las interfaces web (`/` y `/dashboard`), ejecuta los algoritmos de balanceo (Round Robin, Least Connections y GNN-RL) y expone la API de métricas en tiempo real (`/api/metrics`).
2. **`user-svc-1` (Puerto interno 5000):** Réplica 1 del microservicio de consulta de récord académico y datos de estudiantes.
3. **`user-svc-2` (Puerto interno 5000):** Réplica 2 del microservicio de usuarios.
4. **`auth-svc` (Puerto interno 5001):** Microservicio para autenticación e inicio de sesión en el SGA.
5. **`course-svc` (Puerto interno 5003):** Microservicio para inscripción de materias y oferta académica.

---

## 🚀 Algoritmos de Balanceo Implementados

* **Round Robin (`/api/rr/student/record`):** Asigna peticiones de forma cíclica y secuencial a los nodos disponibles.
* **Least Connections (`/api/lc/student/record`):** Evalúa cuál instancia posee el menor número de conexiones activas en el instante de la solicitud.
* **GNN-RL Inteligente (`/api/gnn/student/record`):** Agente de Aprendizaje por Refuerzo basado en el estado del grafo de la red. Toma decisiones de enrutamiento considerando la latencia histórica, saturación y penalizaciones por tiempo de respuesta.

---

## 🛠️ Requisitos Previos

* **Docker** y **Docker Compose**
* **Python 3.9+** (opcional, para ejecutar el script de benchmark localmente)

---

## 📦 Instalación y Despliegue

1. **Clonar el repositorio:**
   ```bash
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
Guillermo Mero - Telemática / FIEC / ESPOL
Saul Quiroz - Telemática / FIEC / ESPOL