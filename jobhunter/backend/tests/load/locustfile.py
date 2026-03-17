"""Load test - simulates typical user workflows."""

from locust import HttpUser, between, task


class JobHunterUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Login and get token."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}

    @task(3)
    def get_companies(self):
        self.client.get("/api/v1/companies", headers=self.headers)

    @task(2)
    def get_dashboard(self):
        self.client.get("/api/v1/candidates/me", headers=self.headers)

    @task(1)
    def get_outreach(self):
        self.client.get("/api/v1/outreach/messages", headers=self.headers)

    @task(1)
    def health_check(self):
        self.client.get("/api/v1/health")
