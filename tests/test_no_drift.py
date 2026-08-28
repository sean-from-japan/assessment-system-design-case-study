"""The interface and the enforcement must never disagree.

This file is the whole point of the redesign, expressed as a test. In the
system this case study examines, one method decided which buttons to show and
a different method carried the action out, and only the first consulted the
user's role. The result was an interface that looked correct over an API that
was not.

Here both come from one table, so the property can be asserted exhaustively:
for every kind, every state, every actor and every action, being offered the
action and being allowed to perform it are the same thing.
"""

from __future__ import annotations

import itertools

import pytest

from assessment_policy.errors import Forbidden, GuardFailed, InvalidTransition
from assessment_policy.model import Action, Kind, State
from assessment_policy.policy import POLICY

from .conftest import AFTER_DEADLINE, EVERYONE, make_assessment

STATES_BY_KIND = {
    kind: sorted(
        {t.source for t in POLICY if t.kind == kind} | {t.target for t in POLICY if t.kind == kind},
        key=str,
    )
    for kind in Kind
}

CASES = [
    (kind, state, actor) for kind in Kind for state in STATES_BY_KIND[kind] for actor in EVERYONE
]


@pytest.mark.parametrize("kind,state,actor", CASES, ids=lambda value: str(value))
def test_offered_actions_are_exactly_the_ones_that_succeed(kind, state, actor, engine_for):
    assessment = make_assessment(kind, state=state, submission_date=AFTER_DEADLINE)
    engine = engine_for(assessment)

    offered = {item.action for item in engine.available_actions(1, actor) if item.enabled}

    accepted = set()
    for action in Action:
        probe = make_assessment(kind, state=state, submission_date=AFTER_DEADLINE)
        probe_engine = engine_for(probe)
        try:
            probe_engine.perform(1, actor, action)
        except (Forbidden, InvalidTransition, GuardFailed):
            continue
        accepted.add(action)

    assert offered == accepted


@pytest.mark.parametrize("kind,state,actor", CASES, ids=lambda value: str(value))
def test_may_agrees_with_perform(kind, state, actor, engine_for):
    for action in Action:
        assessment = make_assessment(kind, state=state, submission_date=AFTER_DEADLINE)
        engine = engine_for(assessment)
        predicted = engine.may(1, actor, action)
        try:
            engine.perform(1, actor, action)
        except (Forbidden, InvalidTransition, GuardFailed):
            actually = False
        else:
            actually = True
        assert predicted == actually, f"{kind} {state} {actor} {action}"


@pytest.mark.parametrize("kind,state", [(k, s) for k in Kind for s in STATES_BY_KIND[k]])
def test_a_refused_action_never_changes_the_state(kind, state, engine_for):
    for actor, action in itertools.product(EVERYONE, Action):
        assessment = make_assessment(kind, state=state, submission_date=AFTER_DEADLINE)
        engine = engine_for(assessment)
        try:
            engine.perform(1, actor, action)
        except (Forbidden, InvalidTransition, GuardFailed):
            assert assessment.state == state


def test_blocked_actions_are_still_explained_rather_than_hidden(engine_for):
    """A guard is a wait, not a refusal, so the interface should say so."""
    from datetime import date

    from .conftest import SUPPORT

    assessment = make_assessment(state=State.RELEASED, submission_date=date(2026, 12, 31))
    engine = engine_for(assessment)
    blocked = [item for item in engine.available_actions(1, SUPPORT) if not item.enabled]
    assert blocked
    assert any("submission" in reason for item in blocked for reason in item.blocked_by)
