import io
import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_upload_resume_pdf(client: AsyncClient, auth_headers: dict):
    # Create a minimal PDF-like content (PyPDF2 will handle real PDFs)
    # For testing, we'll use the endpoint validation
    resp = await client.post(
        f"{API}/candidates/resume",
        headers=auth_headers,
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
    )
    # Should reject non-PDF/DOCX
    assert resp.status_code == 400
    assert "PDF and DOCX" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_too_large(client: AsyncClient, auth_headers: dict):
    # 11MB file
    large_content = b"x" * (11 * 1024 * 1024)
    resp = await client.post(
        f"{API}/candidates/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", large_content, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_dna_before_upload(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/candidates/me/dna", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_skills_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/candidates/me/skills", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []
