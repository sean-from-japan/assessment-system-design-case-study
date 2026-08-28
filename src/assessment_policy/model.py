"""The assessment record, and the vocabulary of states and actions.

There is exactly one set of state names, shared by all three kinds of
assessment. The system examined in this case study had two disjoint state
vocabularies for the same records, defined in two places, and code that could
move an assessment into a state the other half did not recognise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .roles import Actor, Relationship


class Kind(Enum):
    COURSEWORK = "coursework"
    TEST = "test"
    EXAM = "exam"

    def __str__(self) -> str:
        return self.value


class State(Enum):
    DRAFT = "draft"
    PENDING_CHECK = "pending_check"
    CHANGES_REQUESTED = "changes_requested"
    CHECK_APPROVED = "check_approved"
    PENDING_EXAM_OFFICER = "pending_exam_officer"
    EXAM_OFFICER_CHANGES_REQUESTED = "exam_officer_changes_requested"
    PENDING_EXTERNAL_EXAMINER = "pending_external_examiner"
    PENDING_SETTER_RESPONSE = "pending_setter_response"
    PENDING_FINAL_CHECK = "pending_final_check"
    SENT_TO_PRINT = "sent_to_print"
    RELEASED = "released"
    DEADLINE_PASSED = "deadline_passed"
    STANDARDISATION = "standardisation"
    MARKING = "marking"
    ADMIN_CHECK = "admin_check"
    PENDING_MODERATION = "pending_moderation"
    RESULTS_RETURNED = "results_returned"
    MARKS_APPROVED = "marks_approved"

    def __str__(self) -> str:
        return self.value


class Action(Enum):
    SUBMIT_FOR_CHECK = "submit_for_check"
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    RESUBMIT = "resubmit"
    RELEASE = "release"
    SUBMIT_FEEDBACK = "submit_feedback"
    SUBMIT_RESPONSE = "submit_response"
    SEND_TO_PRINT = "send_to_print"
    DEADLINE_PASSED = "deadline_passed"
    START_STANDARDISATION = "start_standardisation"
    START_MARKING = "start_marking"
    RETURN_RESULTS = "return_results"
    ADMIN_CHECK = "admin_check"
    SUBMIT_FOR_MODERATION = "submit_for_moderation"
    COMPLETE_MODERATION = "complete_moderation"
    APPROVE_MARKS = "approve_marks"

    def __str__(self) -> str:
        return self.value


INITIAL_STATE = State.DRAFT
TERMINAL_STATE = State.MARKS_APPROVED


@dataclass
class Assessment:
    """One assessment, as the server holds it.

    The state lives here and nowhere else. Nothing in this package reads a
    state, a setter or a checker from anything a caller sent: the audited
    system decided both the legal transition and the permission from fields
    in the request body, so a caller could nominate themselves as checker in
    the same request that used being the checker to approve the work.
    """

    id: int
    kind: Kind
    state: State = INITIAL_STATE
    setter_id: int | None = None
    checker_id: int | None = None
    moderator_id: int | None = None
    exam_officer_id: int | None = None
    external_examiner_id: int | None = None
    marked_by_team: bool = False
    autograded: bool = False
    submission_date: date | None = None

    def relationships(self, actor: Actor) -> frozenset:
        """Every relationship this actor has to this assessment."""
        holders = {
            Relationship.SETTER: self.setter_id,
            Relationship.CHECKER: self.checker_id,
            Relationship.MODERATOR: self.moderator_id,
            Relationship.EXAM_OFFICER_OF_RECORD: self.exam_officer_id,
            Relationship.EXTERNAL_EXAMINER_OF_RECORD: self.external_examiner_id,
        }
        return frozenset(
            relationship
            for relationship, holder in holders.items()
            if holder is not None and holder == actor.staff_id
        )
