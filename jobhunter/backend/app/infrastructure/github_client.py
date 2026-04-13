import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class GitHubClient:
    def __init__(self) -> None:
        self._base_url = f"https://api.github.com/repos/{settings.GITHUB_REPO}"
        self._headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/issues",
                headers=self._headers,
                json={"title": title, "body": body, "labels": labels},
            )
            response.raise_for_status()
            data = response.json()
            logger.info("github_issue_created", number=data["number"], url=data["html_url"])
            return {"number": data["number"], "url": data["html_url"]}
