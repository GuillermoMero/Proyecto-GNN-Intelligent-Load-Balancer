from locust import HttpUser, task, between

class RoundRobinSGAUser(HttpUser):
    weight = 1
    wait_time = between(1, 2)

    @task(1)
    def login(self):
        self.client.post("/api/sga/login", json={"user": "estudiante", "pass": "123"})

    @task(2)
    def get_record_rr(self):
        self.client.post("/api/rr/student/record", json={"student_id": "12345"})

    @task(1)
    def enroll_course(self):
        self.client.post("/api/courses/enroll", json={"course_code": "FIEC0100"})


class LeastConnectionsSGAUser(HttpUser):
    weight = 1
    wait_time = between(1, 2)

    @task(1)
    def login(self):
        self.client.post("/api/sga/login", json={"user": "estudiante", "pass": "123"})

    @task(2)
    def get_record_lc(self):
        self.client.post("/api/lc/student/record", json={"student_id": "12345"})

    @task(1)
    def enroll_course(self):
        self.client.post("/api/courses/enroll", json={"course_code": "FIEC0100"})


class GNNIntelligentSGAUser(HttpUser):
    weight = 1
    wait_time = between(1, 2)

    @task(1)
    def login(self):
        self.client.post("/api/sga/login", json={"user": "estudiante", "pass": "123"})

    @task(2)
    def get_record_gnn(self):
        self.client.post("/api/gnn/student/record", json={"student_id": "12345"})

    @task(1)
    def enroll_course(self):
        self.client.post("/api/courses/enroll", json={"course_code": "FIEC0100"})