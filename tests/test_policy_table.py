"""Properties the policy table must have, checked over the whole table.

These are the tests that would have failed on the system this study examines.
They are not about any one transition; they are about the table as a whole,
which is the only level at which "some endpoint has no authorisation" is
visible.
"""

from __future__ import annotations

import pytest

from assessment_policy.model import INITIAL_STATE, TERMINAL_STATE, Action, Kind, State
from assessment_policy.policy import POLICY, find, transitions_for, transitions_from


def test_no_transition_is_open_to_everyone():
    """Every row names at least one role or relationship.

    A row with neither would be a state change any authenticated user could
    make. The audited system's workflow endpoint was exactly that.
    """
    unguarded = [t for t in POLICY if not t.roles and not t.relationships]
    assert unguarded == [], [f"{t.kind}:{t.source}--{t.action}" for t in unguarded]


def test_no_state_and_action_pair_is_defined_twice():
    seen = set()
    for transition in POLICY:
        key = (transition.kind, transition.source, transition.action)
        assert key not in seen, key
        seen.add(key)


@pytest.mark.parametrize("kind", list(Kind))
def test_every_state_is_reachable_from_the_start(kind):
    reachable = {INITIAL_STATE}
    changed = True
    while changed:
        changed = False
        for transition in transitions_for(kind):
            if transition.source in reachable and transition.target not in reachable:
                reachable.add(transition.target)
                changed = True
    mentioned = {t.source for t in transitions_for(kind)} | {
        t.target for t in transitions_for(kind)
    }
    assert mentioned - reachable == set(), f"unreachable in {kind}"


@pytest.mark.parametrize("kind", list(Kind))
def test_exactly_one_terminal_state_per_kind(kind):
    states = {t.source for t in transitions_for(kind)} | {t.target for t in transitions_for(kind)}
    terminal = {state for state in states if not transitions_from(kind, state)}
    assert terminal == {TERMINAL_STATE}


@pytest.mark.parametrize("kind", list(Kind))
def test_the_terminal_state_can_be_reached(kind):
    assert any(t.target == TERMINAL_STATE for t in transitions_for(kind))


@pytest.mark.parametrize("kind", list(Kind))
def test_every_kind_starts_by_being_submitted_by_its_setter(kind):
    transition = find(kind, INITIAL_STATE, Action.SUBMIT_FOR_CHECK)
    assert transition is not None
    assert transition.roles == frozenset()


def test_every_action_in_the_enum_is_used_somewhere():
    used = {transition.action for transition in POLICY}
    assert used == set(Action)


def test_every_state_in_the_enum_is_used_somewhere():
    used = {t.source for t in POLICY} | {t.target for t in POLICY}
    assert used == set(State)


def test_each_transition_has_a_label_for_the_interface():
    assert all(transition.label for transition in POLICY)
