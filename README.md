# GNN Intelligent Load Balancer - SGA ESPOL (Simulación)

Sistema de balanceo de carga inteligente diseñado para una **simulación del Sistema de Gestión Académica (SGA) de la Escuela Superior Politécnica del Litoral (ESPOL)**. El proyecto compara estrategias tradicionales de enrutamiento (*Round Robin*, *Least Connections*) frente a un modelo de enrutamiento inteligente basado en Grafos y Aprendizaje por Refuerzo (GNN-RL) implementado de forma eficiente con NumPy.

---

## 📌 Descripción del Proyecto
El proyecto simula un entorno de microservicios distribuido bajo una arquitectura contenedorizada con Docker, emulando la alta concurrencia y la interacción de los estudiantes con los servicios del SGA de la ESPOL. Su objetivo principal es demostrar cómo un enrutador inteligente impulsado por IA puede adaptarse dinámicamente a escenarios de alta congestión (introduciendo retrasos artificiales en nodos específicos) para minimizar la latencia global y garantizar la disponibilidad del servicio.

---

## 🛠️ Prerrequisitos (Requisitos Previos)
Antes de clonar y ejecutar el proyecto en una máquina nueva, asegúrate de tener instalado lo siguiente:
* [Git](https://git-scm.com/) (para clonar el repositorio).
* [Docker Desktop](https://www.docker.com/) (con soporte para Docker Compose, asegurándote de asignarle suficientes recursos de memoria y disco).
* [Python 3.10 o superior](https://www.python.org/) *(Opcional, solo si deseas ejecutar las pruebas de carga de Locust de manera local).*

---

## 📥 Guía de Instalación y Configuración (Desde Cero)

Si eres un usuario nuevo y acabas de clonar el repositorio, sigue estos pasos en tu terminal:

### 1. Clonar el repositorio
Abre tu terminal y ejecuta el siguiente comando para clonar el proyecto:
```bash
git clone <URL-DEL-REPOSITORIO>
cd gnn-load-balancer
2. Levantar la infraestructura con Docker Compose
El sistema simula el ecosistema del SGA mediante múltiples microservicios orquestados en Docker. Para compilar las imágenes y poner en marcha los contenedores en segundo plano, ejecuta:

Bash
docker compose up --build -d
(Nota: Este proceso compilará el balanceador inteligente, los microservicios de autenticación, usuarios, cursos y la base de datos Redis. La primera compilación puede tomar unos minutos).

3. Verificar que los contenedores estén activos
Comprueba que todos los servicios de la simulación estén corriendo correctamente ejecutando:

Bash
docker ps
Deberías ver en la lista los contenedores correspondientes al balanceador, las réplicas del sistema de usuarios del SGA (user-svc-1, user-svc-2), autenticación, cursos y Redis.

🚀 Uso y Pruebas de Rendimiento (Locust)
El proyecto incluye un escenario de pruebas en Locust (locust/locustfile.py) para evaluar el rendimiento concurrente de las tres estrategias de balanceo simulando el tráfico de los estudiantes de la ESPOL.

Pasos para ejecutar las pruebas de carga:
Instalar dependencias de Locust (en tu máquina local):

Bash
pip install locust
Iniciar Locust:
Navega a la carpeta donde se encuentra el archivo de pruebas y ejecuta:

Bash
locust -f locust/locustfile.py
Acceder a la interfaz web de Locust:
Abre tu navegador y entra a: http://localhost:8089

Configurar la prueba en la interfaz:

Number of users: 20 (o la cantidad deseada de usuarios concurrentes simulando estudiantes).

Spawn rate: 2 (usuarios por segundo).

Host: http://localhost:8080 (dirección del balanceador).

Haz clic en Start swarming para iniciar la prueba.

🏗️ Arquitectura del Sistema
load-balancer: Proxy inverso en Flask que expone los endpoints de enrutamiento y aloja el modelo de IA basado en NumPy para la toma de decisiones.

auth-svc: Microservicio de autenticación de usuarios de la simulación del SGA.

user-svc-1 & user-svc-2: Réplicas del microservicio de gestión de usuarios y récords académicos. (Nota: user-svc-2 incluye un retraso artificial de 400ms para simular congestión o saturación del servidor).

course-svc: Microservicio para la gestión e inscripción de materias/cursos.

redis: Almacenamiento en memoria para estados y contadores de la simulación.

📊 Endpoints de Comparación Disponibles
El balanceador expone diferentes rutas para evaluar cada estrategia de enrutamiento en tiempo real bajo la simulación:

POST /api/rr/student/record — Enrutamiento estático (Round Robin).

POST /api/lc/student/record — Enrutamiento reactivo (Least Connections).

POST /api/gnn/student/record — Enrutamiento inteligente (GNN-RL con NumPy).

🛑 Detener el Proyecto
Para apagar y limpiar todos los contenedores de la simulación de manera segura, ejecuta en la raíz del proyecto:

Bash
docker compose down