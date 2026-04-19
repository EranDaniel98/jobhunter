"""Password complexity validator (#102).

Rejects passwords that don't mix uppercase + lowercase + digit, protecting
against weak-password brute-force (login rate limit is not enough at scale).
"""
import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    ChangePasswordRequest,
    RegisterRequest,
    ResetPasswordRequest,
)


def _register(password: str) -> RegisterRequest:
    return RegisterRequest(
        email="test@example.com",
        password=password,
        full_name="Test User",
        invite_code="abc123",
    )


class TestPasswordComplexity:
    def test_accepts_compliant_password(self):
        req = _register("GoodPass1")
        assert req.password == "GoodPass1"

    def test_rejects_all_lowercase(self):
        with pytest.raises(ValidationError) as exc:
            _register("alllower1")
        assert "uppercase" in str(exc.value).lower()

    def test_rejects_all_uppercase(self):
        with pytest.raises(ValidationError) as exc:
            _register("ALLUPPER1")
        assert "lowercase" in str(exc.value).lower()

    def test_rejects_no_digit(self):
        with pytest.raises(ValidationError) as exc:
            _register("NoDigitsHere")
        assert "digit" in str(exc.value).lower()

    def test_rejects_common_weak_password(self):
        with pytest.raises(ValidationError):
            _register("password")  # all-lowercase, no digit

    def test_rejects_numeric_only(self):
        with pytest.raises(ValidationError):
            _register("12345678")

    def test_min_length_still_enforced(self):
        with pytest.raises(ValidationError):
            _register("Aa1")  # has all classes but < 8 chars

    def test_reset_password_rejects_weak(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="tok", new_password="alllower")

    def test_change_password_rejects_weak(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="x", new_password="alllower")
