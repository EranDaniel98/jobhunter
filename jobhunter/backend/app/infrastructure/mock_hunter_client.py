"""In-process mock Hunter.io client for load testing.

Simulates realistic latency (~200ms) and returns canned deterministic data.
Used only when LOADTEST_MODE=True. Never imported in production code paths.
"""
import asyncio


class MockHunterClient:
    """Mock implementation of HunterClientProtocol."""

    _LATENCY = 0.2

    async def domain_search(self, domain: str) -> dict:
        await asyncio.sleep(self._LATENCY)
        return {
            "data": {
                "domain": domain,
                "organization": f"Mock {domain}",
                "emails": [
                    {
                        "value": f"contact@{domain}",
                        "first_name": "Mock",
                        "last_name": "Contact",
                        "position": "Engineering Manager",
                        "confidence": 95,
                    },
                    {
                        "value": f"hr@{domain}",
                        "first_name": "HR",
                        "last_name": "Team",
                        "position": "Recruiter",
                        "confidence": 90,
                    },
                ],
            }
        }

    async def email_finder(self, domain: str, first_name: str, last_name: str) -> dict:
        await asyncio.sleep(self._LATENCY)
        return {
            "data": {
                "email": f"{first_name.lower()}.{last_name.lower()}@{domain}",
                "first_name": first_name,
                "last_name": last_name,
                "score": 92,
                "domain": domain,
            }
        }

    async def email_verifier(self, email: str) -> dict:
        await asyncio.sleep(self._LATENCY)
        return {
            "data": {
                "email": email,
                "status": "valid",
                "result": "deliverable",
                "score": 95,
            }
        }

    async def enrichment(self, email: str) -> dict:
        await asyncio.sleep(self._LATENCY)
        return {
            "data": {
                "email": email,
                "first_name": "Mock",
                "last_name": "User",
                "position": "Senior Engineer",
                "company": "MockCorp",
                "linkedin": "https://linkedin.com/in/mockuser",
            }
        }
