"""Unit tests for resume_service - no real DB, storage, or OpenAI required."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.resume_service import (
    _extract_text_from_docx,
    _extract_text_from_pdf,
    parse_resume,
    upload_resume,
)

# ---------------------------------------------------------------------------
# _extract_text_from_pdf
# ---------------------------------------------------------------------------


class TestExtractTextFromPdf:
    def test_extract_text_from_pdf(self):
        """Extract text from a minimal valid PDF."""
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        # Blank page returns empty string - just verify it doesn't raise
        text = _extract_text_from_pdf(pdf_bytes)
        assert isinstance(text, str)

    def test_extract_text_from_pdf_with_content(self):
        """Patched PdfReader returns page text correctly."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello World"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_text_from_pdf(b"fake-pdf")

        assert result == "Hello World"


# ---------------------------------------------------------------------------
# _extract_text_from_docx
# ---------------------------------------------------------------------------


class TestExtractTextFromDocx:
    def test_extract_text_from_docx(self):
        """Patched Document returns paragraph text correctly."""
        para1 = MagicMock()
        para1.text = "First paragraph"
        para2 = MagicMock()
        para2.text = "Second paragraph"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_text_from_docx(b"fake-docx")

        assert result == "First paragraph\nSecond paragraph"

    def test_extract_text_from_docx_empty(self):
        """Empty document returns empty string."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_text_from_docx(b"fake-docx")

        assert result == ""


# ---------------------------------------------------------------------------
# upload_resume
# ---------------------------------------------------------------------------


class TestUploadResume:
    @pytest.mark.asyncio
    async def test_upload_resume_pdf_success(self):
        """PDF upload creates Resume with correct fields."""
        candidate_id = uuid.uuid4()
        file_bytes = b"fake-pdf-content"
        filename = "myresume.pdf"

        db = AsyncMock()
        db.execute.return_value = MagicMock()

        mock_storage = AsyncMock()
        mock_storage.upload.return_value = "resumes/key.pdf"

        with (
            patch("app.services.resume_service.get_storage", return_value=mock_storage),
            patch(
                "app.services.resume_service._extract_text_from_pdf",
                return_value="Extracted PDF text",
            ),
        ):
            await upload_resume(db, candidate_id, file_bytes, filename)

        mock_storage.upload.assert_awaited_once()
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        added = db.add.call_args[0][0]
        assert added.candidate_id == candidate_id
        assert added.raw_text == "Extracted PDF text"
        assert added.is_primary is True

    @pytest.mark.asyncio
    async def test_upload_resume_docx_success(self):
        """DOCX upload creates Resume with correct fields."""
        candidate_id = uuid.uuid4()
        file_bytes = b"fake-docx-content"
        filename = "myresume.docx"

        db = AsyncMock()
        db.execute.return_value = MagicMock()

        mock_storage = AsyncMock()
        mock_storage.upload.return_value = "resumes/key.docx"

        with (
            patch("app.services.resume_service.get_storage", return_value=mock_storage),
            patch(
                "app.services.resume_service._extract_text_from_docx",
                return_value="Extracted DOCX text",
            ),
        ):
            await upload_resume(db, candidate_id, file_bytes, filename)

        added = db.add.call_args[0][0]
        assert added.raw_text == "Extracted DOCX text"

    @pytest.mark.asyncio
    async def test_upload_resume_invalid_type(self):
        """Unsupported file extension raises ValueError."""
        db = AsyncMock()
        with pytest.raises(ValueError, match="Only PDF and DOCX"):
            await upload_resume(db, uuid.uuid4(), b"data", "notes.txt")

    @pytest.mark.asyncio
    async def test_upload_resume_marks_previous_nonprimary(self):
        """UPDATE query is issued to mark previous resumes as non-primary."""
        candidate_id = uuid.uuid4()
        db = AsyncMock()
        db.execute.return_value = MagicMock()

        mock_storage = AsyncMock()

        with (
            patch("app.services.resume_service.get_storage", return_value=mock_storage),
            patch(
                "app.services.resume_service._extract_text_from_pdf",
                return_value="text",
            ),
        ):
            await upload_resume(db, candidate_id, b"pdf", "r.pdf")

        # db.execute should have been called at least once (for the UPDATE)
        assert db.execute.await_count >= 1


# ---------------------------------------------------------------------------
# parse_resume
# ---------------------------------------------------------------------------


class TestParseResume:
    @pytest.mark.asyncio
    async def test_parse_resume_success(self):
        """parse_resume calls OpenAI and saves parsed_data."""
        resume = MagicMock()
        resume.raw_text = "John Doe\nSoftware Engineer at Acme"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = resume

        db = AsyncMock()
        db.execute.return_value = result_mock

        parsed_output = {
            "name": "John Doe",
            "headline": "Software Engineer",
            "experiences": [],
            "skills": ["Python"],
            "education": [],
            "certifications": [],
            "summary": "Experienced engineer.",
        }

        mock_openai = AsyncMock()
        mock_openai.parse_structured.return_value = parsed_output

        with patch("app.services.resume_service.get_openai", return_value=mock_openai):
            await parse_resume(db, uuid.uuid4())

        assert resume.parsed_data == parsed_output
        db.commit.assert_awaited_once()
        mock_openai.parse_structured.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parse_resume_not_found(self):
        """Non-existent resume_id raises ValueError."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Resume not found"):
            await parse_resume(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_parse_resume_no_text(self):
        """Resume without raw_text raises ValueError."""
        resume = MagicMock()
        resume.raw_text = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = resume

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="no extracted text"):
            await parse_resume(db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_parse_resume_empty_text(self):
        """Resume with empty raw_text raises ValueError."""
        resume = MagicMock()
        resume.raw_text = ""

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = resume

        db = AsyncMock()
        db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="no extracted text"):
            await parse_resume(db, uuid.uuid4())
