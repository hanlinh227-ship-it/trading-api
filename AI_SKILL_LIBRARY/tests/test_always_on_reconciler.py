"""Offline tests for pure deterministic always-on reconciliation."""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v4.always_on.reconciler import (  # noqa: E402
    EXCLUDE_STALE_WORKER,
    QUARANTINE_PROVIDER,
    REQUEUE_EXPIRED_LEASE,
    REQUEST_REPLICA_REPAIR,
    reconcile,
)


def test_no_drift_no_actions():
    desired = {
        "leases": [{"id": "l1"}],
        "providers": [{"id": "p1"}],
        "replicas": [{"id": "r1"}],
        "workers": [{"id": "w1"}],
    }
    observed = {
        "leases": [{"id": "l1"}],
        "providers": [{"id": "p1", "healthy": True}],
        "replicas": [{"id": "r1", "healthy": True}],
        "workers": [{"id": "w1", "stale": False}],
    }
    assert reconcile(desired, observed) == []


def test_missing_desired_entries_emit_actions():
    desired = {
        "leases": [{"id": "l1"}],
        "providers": [{"id": "p1"}],
        "replicas": [{"id": "r1"}],
        "workers": [{"id": "w1"}],
    }
    observed = {"leases": [], "providers": [], "replicas": [], "workers": []}
    actions = reconcile(desired, observed)
    names = {a["action"] for a in actions}
    assert names == {
        REQUEUE_EXPIRED_LEASE,
        QUARANTINE_PROVIDER,
        REQUEST_REPLICA_REPAIR,
        EXCLUDE_STALE_WORKER,
    }


def test_expired_lease_and_unhealthy_entries():
    desired = {}
    observed = {
        "leases": [{"id": "l1", "expired": True}],
        "providers": [{"id": "p1", "healthy": False}],
        "replicas": [{"id": "r1", "healthy": False}],
        "workers": [{"id": "w1", "stale": True}],
    }
    actions = reconcile(desired, observed)
    assert actions == [
        {"action": REQUEUE_EXPIRED_LEASE, "target": "l1", "reason": "observed lease expired"},
        {"action": QUARANTINE_PROVIDER, "target": "p1", "reason": "observed provider unhealthy"},
        {"action": REQUEST_REPLICA_REPAIR, "target": "r1", "reason": "observed replica unhealthy"},
        {"action": EXCLUDE_STALE_WORKER, "target": "w1", "reason": "observed worker stale"},
    ]


def test_deterministic_and_deduplicated():
    desired = {
        "leases": [{"id": "l1"}, {"id": "l1"}],
        "providers": [{"id": "p1"}, {"id": "p1"}],
        "replicas": [{"id": "r1"}, {"id": "r1"}],
        "workers": [{"id": "w1"}, {"id": "w1"}],
    }
    observed = {
        "leases": [{"id": "l1", "expired": True}],
        "providers": [{"id": "p1", "healthy": False}],
        "replicas": [{"id": "r1", "healthy": False}],
        "workers": [{"id": "w1", "stale": True}],
    }
    first = reconcile(desired, observed)
    second = reconcile(desired, observed)
    assert first == second
    keys = [(a["action"], a["target"]) for a in first]
    assert len(keys) == len(set(keys))


def test_inputs_not_mutated():
    desired = {"leases": [{"id": "l1"}], "providers": [], "replicas": [], "workers": []}
    observed = {"leases": [], "providers": [], "replicas": [], "workers": []}
    desired_before = copy.deepcopy(desired)
    observed_before = copy.deepcopy(observed)
    reconcile(desired, observed)
    assert desired == desired_before
    assert observed == observed_before


def test_malformed_inputs_fail_closed():
    assert reconcile(None, None) == []
    assert reconcile("bad", 7) == []
    assert reconcile({"leases": "bad"}, {"leases": None}) == []
    assert reconcile({"leases": [None, 3, {"id": ""}]}, {}) == []


def test_unknown_action_names_never_emitted():
    desired = {"leases": [{"id": "l1"}]}
    observed = {}
    actions = reconcile(desired, observed)
    allowed = {
        REQUEUE_EXPIRED_LEASE,
        QUARANTINE_PROVIDER,
        REQUEST_REPLICA_REPAIR,
        EXCLUDE_STALE_WORKER,
    }
    assert all(a["action"] in allowed for a in actions)
