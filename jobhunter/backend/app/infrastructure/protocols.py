from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OpenAIClientProtocol(Protocol):
    async def parse_structured(
        self, system_prompt: str, user_content: str, response_schema: dict
    ) -> dict:
        """Send a prompt and get structured JSON output."""
        ...

    async def embed(self, text: str, dimensions: int = 1536) -> list[float]:
        """Generate an embedding vector for the given text."""
        ...

    async def batch_embed(self, texts: list[str], dimensions: int = 1536) -> list[list[float]]:
        """Generate embedding vectors for multiple texts in a single API call."""
        ...

    async def chat(self, messages: list[dict]) -> str:
        """Send a chat message and get a text response."""
        ...

    async def vision(self, messages: list[dict], images: list[bytes]) -> str:
        """Send a message with images and get a text response."""
        ...


@runtime_checkable
class HunterClientProtocol(Protocol):
    async def domain_search(self, domain: str) -> dict:
        """Search for email addresses at a domain."""
        ...

    async def email_finder(self, domain: str, first_name: str, last_name: str) -> dict:
        """Find the email address of a specific person."""
        ...

    async def email_verifier(self, email: str) -> dict:
        """Verify an email address."""
        ...

    async def enrichment(self, email: str) -> dict:
        """Get enrichment data for an email address."""
        ...


@runtime_checkable
class EmailClientProtocol(Protocol):
    async def send(
        self,
        to: str,
        from_email: str,
        subject: str,
        body: str,
        tags: list[str] | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Send an email. Returns dict with 'id' key."""
        ...

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Verify and parse a webhook payload. Raises on invalid signature."""
        ...
