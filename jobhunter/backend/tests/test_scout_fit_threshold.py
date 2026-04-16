"""Verify SCOUT_FIT_THRESHOLD is a config setting and score_and_filter respects it."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings


def test_scout_fit_threshold_defaults_to_025():
    """Default threshold should be 0.25 — tuned for cross-domain (resume vs. news)
    embedding similarity, which runs much lower than same-domain cosine scores.
    Regression guard: 2026-04-16 prod audit showed 0.55 rejected 100% of real data
    (actual scores ranged 0.09-0.32)."""
    assert settings.SCOUT_FIT_THRESHOLD == 0.25


@pytest.mark.asyncio
async def test_score_and_filter_uses_config_threshold(monkeypatch):
    """Changing SCOUT_FIT_THRESHOLD should change which companies pass scoring."""
    from app.graphs import scout_pipeline

    # Candidate with DNA embedding
    mock_dna = MagicMock()
    mock_dna.embedding = [0.1] * 1536

    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    call_count = 0

    def exec_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        r = MagicMock()
        if call_count == 1:
            r.scalar_one_or_none = MagicMock(return_value=mock_dna)
        else:
            r.all = MagicMock(return_value=[])
        return r

    mock_session.execute = AsyncMock(side_effect=exec_side_effect)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)

    # Fabricate a signal whose precomputed embedding gives cosine ~= 0.4 against DNA
    state = {
        "candidate_id": str(uuid.uuid4()),
        "plan_tier": "hunter",
        "parsed_companies": [
            {
                "company_name": "X",
                "estimated_domain": "x.co",
                "description": "d",
                "industry": "i",
                # This embedding has cosine ~= 0.4 with [0.1]*1536 (we fabricate via scaling)
                "_precomputed_embedding": [0.04] * 1536,  # cosine with [0.1]*1536 == 1.0
            }
        ],
        "scored_companies": None,
        "companies_created": 0,
        "status": "pending",
        "error": None,
    }

    with patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=cm):
        # At threshold 0.9, cosine==1.0 still passes (sanity check)
        monkeypatch.setattr(settings, "SCOUT_FIT_THRESHOLD", 0.9)
        result_high = await scout_pipeline.score_and_filter_node(state)

    assert len(result_high["scored_companies"]) == 1

    # Reset DB mock call count
    call_count = 0

    with patch("app.graphs.scout_pipeline._db_mod.async_session_factory", return_value=cm):
        # At threshold 1.1 (impossible), cosine==1.0 is rejected
        monkeypatch.setattr(settings, "SCOUT_FIT_THRESHOLD", 1.1)
        result_impossible = await scout_pipeline.score_and_filter_node(state)

    assert len(result_impossible["scored_companies"]) == 0
