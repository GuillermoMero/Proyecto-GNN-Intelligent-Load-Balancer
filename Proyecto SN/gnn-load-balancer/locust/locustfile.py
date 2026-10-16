from locust import HttpUser, task, between

class CloudSystemUser(HttpUser):
    # Tiempo de espera entre peticiones por usuario simulado (1 a 3 segundos)
    wait_time = between(1, 3)

    @task(3)
    def test_users_endpoint(self):
        # Tarea con mayor peso (3) para probar el balanceo de carga (Round Robin)
        self.client.get("/users")

    @task(1)
    def test_auth_endpoint(self):
        self.client.get("/auth")

    @task(1)
    def test_products_endpoint(self):
        self.client.get("/products")