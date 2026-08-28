"""Roles as a set, and relationships as a separate question."""

from __future__ import annotations

import pytest

from assessment_policy.model import Kind
from assessment_policy.roles import Actor, Relationship, Role

from .conftest import CHECKER, SETTER, make_assessment


def test_roles_are_a_set_not_a_delimited_string():
    """Substring matching over a joined role string was the audited bug.

    With a set, no role name can be a prefix or suffix of another by accident.
    """
    actor = Actor(1, [Role.ACADEMIC])
    assert actor.has_role(Role.ACADEMIC)
    assert not actor.has_role(Role.EXTERNAL_EXAMINER)
    assert "academic" not in set(actor.roles)


def test_a_role_cannot_be_smuggled_in_as_a_string():
    with pytest.raises(TypeError):
        Actor(1, ["exam_officer"])


def test_relationships_are_per_assessment():
    assessment = make_assessment(Kind.EXAM)
    assert assessment.relationships(SETTER) == frozenset({Relationship.SETTER})
    assert assessment.relationships(CHECKER) == frozenset({Relationship.CHECKER})


def test_one_person_can_hold_two_relationships_to_one_assessment():
    assessment = make_assessment(setter_id=1, checker_id=1)
    actor = Actor(1, [Role.ACADEMIC])
    assert assessment.relationships(actor) == frozenset({Relationship.SETTER, Relationship.CHECKER})


def test_an_unassigned_slot_grants_nothing():
    """A None field must not match an actor, however the ids compare."""
    assessment = make_assessment(checker_id=None, moderator_id=None)
    actor = Actor(1, [Role.ACADEMIC])
    assert Relationship.CHECKER not in assessment.relationships(actor)


def test_someone_with_no_relationship_has_none():
    assessment = make_assessment()
    assert assessment.relationships(Actor(999, [Role.ACADEMIC])) == frozenset()
