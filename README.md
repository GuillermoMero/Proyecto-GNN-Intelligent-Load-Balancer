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