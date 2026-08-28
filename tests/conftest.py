from __future__ import annotations

from datetime import date

import pytest

from assessment_policy.engine import WorkflowEngine
from assessment_policy.model import Assessment, Kind
from assessment_policy.roles import Actor, Role
from assessment_policy.store import AssessmentStore

TODAY = date(2026, 6, 1)
BEFORE_DEADLINE = date(2026, 7, 1)
AFTER_DEADLINE = date(2026, 5, 1)

SETTER = Actor(1, [Role.ACADEMIC])
CHECKER = Actor(2, [Role.ACADEMIC])
MODERATOR = Actor(3, [Role.ACADEMIC])
EXAM_OFFICER = Actor(4, [Role.ACADEMIC, Role.EXAM_OFFICER])
EXTERNAL = Actor(5, [Role.EXTERNAL_EXAMINER])
SUPPORT = Actor(6, [Role.TEACHING_SUPPORT])
ADMIN = Actor(7, [Role.ADMIN_TEAM])
OUTSIDER = Actor(99, [Role.ACADEMIC])

EVERYONE = [SETTER, CHECKER, MODERATOR, EXAM_OFFICER, EXTERNAL, SUPPORT, ADMIN, OUTSIDER]


def make_assessment(kind: Kind = Kind.COURSEWORK, **overrides) -> Assessment:
    fields = {
        "id": 1,
        "kind": kind,
        "setter_id": SETTER.staff_id,
        "checker_id": CHECKER.staff_id,
        "moderator_id": MODERATOR.staff_id,
        "exam_officer_id": EXAM_OFFICER.staff_id,
        "external_examiner_id": EXTERNAL.staff_id,
        "submission_date": AFTER_DEADLINE,
    }
    fields.update(overrides)
    return Assessment(**fields)


@pytest.fixture
def engine_for():
    def build(assessment, today: date = TODAY) -> WorkflowEngine:
        return WorkflowEngine(AssessmentStore([assessment]), clock=lambda: today)

    return build
