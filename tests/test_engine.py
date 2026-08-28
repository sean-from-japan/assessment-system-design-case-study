"""The behaviour of the engine, including the defects it is designed against."""

from __future__ import annotations

import pytest

from assessment_policy.errors import Forbidden, GuardFailed, InvalidTransition, NotFound
from assessment_policy.model import Action, Kind, State
from assessment_policy.roles import Actor, Role

from .conftest import (
    ADMIN,
    AFTER_DEADLINE,
    BEFORE_DEADLINE,
    CHECKER,
    EXAM_OFFICER,
    EXTERNAL,
    MODERATOR,
    OUTSIDER,
    SETTER,
    SUPPORT,
    TODAY,
    make_assessment,
)


def test_the_setter_can_submit_a_draft(engine_for):
    assessment = make_assessment()
    engine = engine_for(assessment)
    applied = engine.perform(1, SETTER, Action.SUBMIT_FOR_CHECK)
    assert applied.previous == State.DRAFT
    assert applied.current == State.PENDING_CHECK
    assert assessment.state == State.PENDING_CHECK


def test_someone_unrelated_cannot_submit_it(engine_for):
    assessment = make_assessment()
    engine = engine_for(assessment)
    with pytest.raises(Forbidden, match="setter"):
        engine.perform(1, OUTSIDER, Action.SUBMIT_FOR_CHECK)
    assert assessment.state == State.DRAFT, "a refused action must not change state"


def test_the_setter_cannot_approve_their_own_work(engine_for):
    """Separation of duties, which is the entire reason this workflow exists."""
    assessment = make_assessment(state=State.PENDING_CHECK)
    engine = engine_for(assessment)
    with pytest.raises(Forbidden):
        engine.perform(1, SETTER, Action.APPROVE)


def test_a_checker_on_another_assessment_cannot_approve_this_one(engine_for):
    assessment = make_assessment(state=State.PENDING_CHECK, checker_id=42)
    engine = engine_for(assessment)
    # CHECKER holds no special role: their power came from the relationship.
    with pytest.raises(Forbidden):
        engine.perform(1, CHECKER, Action.APPROVE)


def test_an_action_that_does_not_exist_here_is_a_different_error(engine_for):
    """ "You may not" and "that is not possible" are not the same refusal."""
    assessment = make_assessment(state=State.DRAFT)
    engine = engine_for(assessment)
    with pytest.raises(InvalidTransition):
        engine.perform(1, SETTER, Action.APPROVE_MARKS)


def test_a_missing_assessment_is_reported(engine_for):
    engine = engine_for(make_assessment())
    with pytest.raises(NotFound):
        engine.perform(999, SETTER, Action.SUBMIT_FOR_CHECK)


def test_the_deadline_guard_blocks_before_the_date_and_allows_after(engine_for):
    """The audited system had this comparison inverted."""
    assessment = make_assessment(state=State.RELEASED, submission_date=BEFORE_DEADLINE)
    engine = engine_for(assessment, today=TODAY)
    with pytest.raises(GuardFailed, match="submission"):
        engine.perform(1, SUPPORT, Action.DEADLINE_PASSED)

    assessment.submission_date = AFTER_DEADLINE
    engine.perform(1, SUPPORT, Action.DEADLINE_PASSED)
    assert assessment.state == State.DEADLINE_PASSED


def test_an_assessment_with_no_date_recorded_does_not_pass_the_deadline_gate(engine_for):
    assessment = make_assessment(state=State.RELEASED, submission_date=None)
    engine = engine_for(assessment)
    with pytest.raises(GuardFailed, match="not recorded"):
        engine.perform(1, SUPPORT, Action.DEADLINE_PASSED)


def test_a_permitted_actor_blocked_by_a_guard_is_not_a_permission_error(engine_for):
    assessment = make_assessment(state=State.RELEASED, submission_date=BEFORE_DEADLINE)
    engine = engine_for(assessment)
    with pytest.raises(GuardFailed):
        engine.perform(1, SUPPORT, Action.DEADLINE_PASSED)


def test_team_marked_work_goes_through_standardisation(engine_for):
    assessment = make_assessment(state=State.DEADLINE_PASSED, marked_by_team=True)
    engine = engine_for(assessment)
    with pytest.raises(GuardFailed, match="standardisation comes first"):
        engine.perform(1, SETTER, Action.START_MARKING)
    engine.perform(1, SETTER, Action.START_STANDARDISATION)
    assert assessment.state == State.STANDARDISATION


def test_work_marked_alone_skips_standardisation(engine_for):
    assessment = make_assessment(state=State.DEADLINE_PASSED, marked_by_team=False)
    engine = engine_for(assessment)
    with pytest.raises(GuardFailed, match="nothing to standardise"):
        engine.perform(1, SETTER, Action.START_STANDARDISATION)
    engine.perform(1, SETTER, Action.START_MARKING)
    assert assessment.state == State.MARKING


def test_an_autograded_test_returns_results_without_marking(engine_for):
    assessment = make_assessment(Kind.TEST, state=State.DEADLINE_PASSED, autograded=True)
    engine = engine_for(assessment)
    engine.perform(1, SUPPORT, Action.RETURN_RESULTS)
    assert assessment.state == State.RESULTS_RETURNED


def test_a_hand_marked_test_cannot_skip_to_results(engine_for):
    assessment = make_assessment(Kind.TEST, state=State.DEADLINE_PASSED, autograded=False)
    engine = engine_for(assessment)
    with pytest.raises(GuardFailed, match="not autograded"):
        engine.perform(1, SUPPORT, Action.RETURN_RESULTS)


def test_an_exam_needs_the_exam_officer_as_well_as_the_checker(engine_for):
    assessment = make_assessment(Kind.EXAM, state=State.PENDING_CHECK)
    engine = engine_for(assessment)
    engine.perform(1, CHECKER, Action.APPROVE)
    assert assessment.state == State.PENDING_EXAM_OFFICER
    with pytest.raises(Forbidden):
        engine.perform(1, CHECKER, Action.APPROVE)
    engine.perform(1, EXAM_OFFICER, Action.APPROVE)
    assert assessment.state == State.PENDING_EXTERNAL_EXAMINER


def test_holding_the_exam_officer_role_is_not_enough_without_being_this_papers_officer(engine_for):
    """A standing role does not grant a per-assessment permission."""
    other_officer = Actor(77, [Role.ACADEMIC, Role.EXAM_OFFICER])
    assessment = make_assessment(Kind.EXAM, state=State.PENDING_EXAM_OFFICER)
    engine = engine_for(assessment)
    with pytest.raises(Forbidden):
        engine.perform(1, other_officer, Action.APPROVE)


def test_the_external_examiner_stage_cannot_be_skipped(engine_for):
    assessment = make_assessment(Kind.EXAM, state=State.PENDING_EXTERNAL_EXAMINER)
    engine = engine_for(assessment)
    with pytest.raises(InvalidTransition):
        engine.perform(1, EXAM_OFFICER, Action.SEND_TO_PRINT)
    engine.perform(1, EXTERNAL, Action.SUBMIT_FEEDBACK)
    assert assessment.state == State.PENDING_SETTER_RESPONSE


def test_a_full_exam_run_reaches_approved_marks(engine_for):
    assessment = make_assessment(Kind.EXAM, submission_date=AFTER_DEADLINE)
    engine = engine_for(assessment)
    for actor, action in [
        (SETTER, Action.SUBMIT_FOR_CHECK),
        (CHECKER, Action.APPROVE),
        (EXAM_OFFICER, Action.APPROVE),
        (EXTERNAL, Action.SUBMIT_FEEDBACK),
        (SETTER, Action.SUBMIT_RESPONSE),
        (EXAM_OFFICER, Action.SEND_TO_PRINT),
        (SUPPORT, Action.DEADLINE_PASSED),
        (SETTER, Action.START_MARKING),
        (ADMIN, Action.ADMIN_CHECK),
        (ADMIN, Action.SUBMIT_FOR_MODERATION),
        (MODERATOR, Action.APPROVE_MARKS),
    ]:
        engine.perform(1, actor, action)
    assert assessment.state == State.MARKS_APPROVED


def test_a_full_coursework_run_reaches_approved_marks(engine_for):
    assessment = make_assessment(submission_date=AFTER_DEADLINE)
    engine = engine_for(assessment)
    for actor, action in [
        (SETTER, Action.SUBMIT_FOR_CHECK),
        (CHECKER, Action.APPROVE),
        (SUPPORT, Action.RELEASE),
        (SUPPORT, Action.DEADLINE_PASSED),
        (SETTER, Action.START_MARKING),
        (SETTER, Action.SUBMIT_FOR_MODERATION),
        (MODERATOR, Action.COMPLETE_MODERATION),
        (SUPPORT, Action.APPROVE_MARKS),
    ]:
        engine.perform(1, actor, action)
    assert assessment.state == State.MARKS_APPROVED


def test_nothing_more_can_happen_once_marks_are_approved(engine_for):
    assessment = make_assessment(state=State.MARKS_APPROVED)
    engine = engine_for(assessment)
    for action in Action:
        with pytest.raises(InvalidTransition):
            engine.perform(1, SUPPORT, action)
