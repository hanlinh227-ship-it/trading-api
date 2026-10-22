from datetime import datetime, timezone

import pytest

from stackhub.source_capabilities import SourceCapabilities, assert_source_eligible_for


def test_rejects_external_spend_source():
    capabilities = SourceCapabilities(
        agent_allowed=True,
        auto_discovery=True,
        external_spend_required=True,
    )
    with pytest.raises(ValueError):
        assert_source_eligible_for("discover", capabilities)


def test_rejects_unverified_mutation():
    capabilities = SourceCapabilities(
        agent_allowed=True,
        auto_discovery=True,
        auto_claim=True,
    )
    with pytest.raises(ValueError):
        assert_source_eligible_for("claim", capabilities)


def test_allows_verified_claim():
    now = datetime.now(timezone.utc)
    capabilities = SourceCapabilities(
        agent_allowed=True,
        auto_discovery=True,
        auto_claim=True,
        mutation_verified_at=now,
        terms_verified_at=now,
    )
    assert_source_eligible_for("claim", capabilities)
