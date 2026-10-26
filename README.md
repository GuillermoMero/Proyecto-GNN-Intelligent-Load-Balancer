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