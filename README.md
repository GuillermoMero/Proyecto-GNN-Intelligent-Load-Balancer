# GNN Intelligent Load Balancer (Cloud Systems)

Proyecto desarrollado para la materia de **Sistemas en la Nube** en la **Escuela Superior Politécnica del Litoral (ESPOL)**. Consiste en una arquitectura de microservicios basada en contenedores Docker, gobernada por un API Gateway/Load Balancer inicial (baseline con algoritmo **Round Robin**) y evaluada mediante pruebas de carga automatizadas.

---

## 🏗️ Arquitectura del Sistema

El sistema está compuesto por los siguientes servicios desacoplados:
* **Load Balancer (API Gateway):** Puerto `8080`. Implementa la lógica de enrutamiento y distribución de tráfico.
* **Auth Service (`auth-svc`):** Microservicio encargado de la gestión y validación de tokens de autenticación.
* **User Service (`user-svc`):** Microservicio desplegado con **múltiples réplicas** (`user-svc-1`, `user-svc-2`) para demostrar el balanceo de carga.
* **Product Service (`product-svc`):** Microservicio que gestiona el catálogo de productos.
* **Redis Cache:** Servicio de caché integrado en la infraestructura cloud.

---

## 🛠️ Tecnologías Utilizadas

* **Orquestación:** Docker & Docker Compose
* **Backend:** Python (Flask)
* **Pruebas de Carga:** Locust

---

## 🚀 Guía de Instalación y Despliegue Local

Sigue estos pasos para levantar el entorno completo en tu máquina:

### 1. Clonar el repositorio
```bash
git clone <URL_DE_TU_REPOSITORIO>
cd gnn-load-balancer


2. Levantar la infraestructura con Docker Compose
Asegúrate de tener Docker Desktop abierto y ejecuta en la raíz del proyecto:

Bash
docker compose up --build -d
3. Verificar los servicios
Puedes comprobar que las peticiones se distribuyen correctamente entre las réplicas ejecutando:

Bash
curl http://localhost:8080/users
curl http://localhost:8080/auth
curl http://localhost:8080/products
📈 Pruebas de Carga y Simulación de Tráfico (Locust)
Para simular escenarios de carga (baja, alta y concurrencia) sobre el balanceador:

Crear y activar un entorno virtual de Python:

Bash
python -m venv venv
source venv/Scripts/Activate  # En Windows (PowerShell: .\venv\Scripts\Activate)
Instalar Locust:

Bash
pip install locust
Ejecutar la herramienta apuntando al archivo de pruebas:

Bash
locust -f locust/locustfile.py --host http://localhost:8080
Abre tu navegador web y accede a http://localhost:8089 para configurar los usuarios concurrentes y visualizar las métricas en tiempo real.

🛑 Detener el Proyecto
Para apagar los contenedores de manera limpia y liberar puertos:

Bash
docker compose down