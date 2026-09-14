import pytest

from money_ecosystem.render_gateway.state import InvalidTransition, JobState, transition


def test_happy_path_transitions_are_allowed():
    path = [
        JobState.RECEIVED,
        JobState.ASSETS_STAGED,
        JobState.VALIDATED,
        JobState.ROUTED,
        JobState.QUEUED,
        JobState.RENDERING,
        JobState.QA,
        JobState.PACKAGING,
        JobState.RETURNING,
        JobState.COMPLETE,
    ]
    current = path[0]
    for target in path[1:]:
        current = transition(current, target)
    assert current is JobState.COMPLETE


def test_complete_requires_returning_path():
    with pytest.raises(InvalidTransition):
        transition(JobState.QA, JobState.COMPLETE)


def test_failure_state_can_be_entered_from_non_terminal_state():
    assert transition(JobState.ROUTED, JobState.QUALITY_TARGET_UNAVAILABLE) is JobState.QUALITY_TARGET_UNAVAILABLE


def test_terminal_state_cannot_transition():
    with pytest.raises(InvalidTransition):
        transition(JobState.COMPLETE, JobState.RECEIVED)
