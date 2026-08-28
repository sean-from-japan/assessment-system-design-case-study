"""The workflow: every legal transition, and who may perform it.

This table is the single source of truth. Both questions the system has to
answer come from it:

* *What may this person do now?* — filter the table.
* *May this person do this?* — look the row up in the table.

They cannot disagree, because there is nothing for them to disagree about.
That is the central correction this design makes. In the system examined in
the case study, the first question was answered by a method that consulted
roles and relationships, and the second by a method that consulted nothing at
all, so the user interface hid actions the API would still carry out.

Every row names at least one role or relationship. A row with no principals
would be a transition anyone could make, and a test rejects the table if one
ever appears.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .model import Action, Assessment, Kind, State
from .roles import Relationship, Role


@dataclass(frozen=True)
class Guard:
    """A precondition of the domain, separate from the question of permission.

    Kept apart from authorisation so that a refusal can say which one it was:
    "you are not the checker" and "the submission date has not passed" are
    different problems with different fixes.
    """

    name: str
    holds: Callable[[Assessment, date], bool]
    explanation: str


def _deadline_reached(assessment: Assessment, today: date) -> bool:
    # The audited system had this comparison the wrong way round, and rejected
    # exactly the assessments whose deadline had in fact passed.
    if assessment.submission_date is None:
        return False
    return today >= assessment.submission_date


DEADLINE_REACHED = Guard(
    "deadline_reached",
    _deadline_reached,
    "the submission or sitting date has not been reached, or is not recorded",
)
MARKED_BY_TEAM = Guard(
    "marked_by_team",
    lambda assessment, today: assessment.marked_by_team,
    "this assessment is not marked by a team, so there is nothing to standardise",
)
MARKED_ALONE = Guard(
    "marked_alone",
    lambda assessment, today: not assessment.marked_by_team,
    "this assessment is marked by a team, so standardisation comes first",
)
AUTOGRADED = Guard(
    "autograded",
    lambda assessment, today: assessment.autograded,
    "this test is not autograded, so results cannot be returned without marking",
)
MARKED_BY_HAND = Guard(
    "marked_by_hand",
    lambda assessment, today: not assessment.autograded,
    "this test is autograded, so it does not go through marking",
)


@dataclass(frozen=True)
class Transition:
    kind: Kind
    source: State
    action: Action
    target: State
    label: str
    roles: frozenset[Role] = frozenset()
    relationships: frozenset[Relationship] = frozenset()
    guards: tuple[Guard, ...] = ()

    def principals(self) -> str:
        names = [str(role) for role in sorted(self.roles, key=str)]
        names += [str(rel) for rel in sorted(self.relationships, key=str)]
        return " or ".join(names)


def _t(
    kind: Kind,
    source: State,
    action: Action,
    target: State,
    label: str,
    roles: tuple[Role, ...] = (),
    relationships: tuple[Relationship, ...] = (),
    guards: tuple[Guard, ...] = (),
) -> Transition:
    return Transition(
        kind=kind,
        source=source,
        action=action,
        target=target,
        label=label,
        roles=frozenset(roles),
        relationships=frozenset(relationships),
        guards=guards,
    )


def _SETTING(kind):
    return [
        _t(
            kind,
            State.DRAFT,
            Action.SUBMIT_FOR_CHECK,
            State.PENDING_CHECK,
            "Submit for checking",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.PENDING_CHECK,
            Action.REQUEST_CHANGES,
            State.CHANGES_REQUESTED,
            "Request changes",
            relationships=(Relationship.CHECKER,),
        ),
        _t(
            kind,
            State.CHANGES_REQUESTED,
            Action.RESUBMIT,
            State.PENDING_CHECK,
            "Resubmit for checking",
            relationships=(Relationship.SETTER,),
        ),
    ]


def _marking(kind: Kind, after: State, moderation_target: State) -> list[Transition]:
    """The shared tail: standardise or not, mark, moderate, approve."""
    return [
        _t(
            kind,
            after,
            Action.START_STANDARDISATION,
            State.STANDARDISATION,
            "Start marking standardisation",
            relationships=(Relationship.SETTER,),
            roles=(Role.TEACHING_SUPPORT,),
            guards=(MARKED_BY_TEAM,),
        ),
        _t(
            kind,
            after,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
            guards=(MARKED_ALONE,),
        ),
        _t(
            kind,
            State.STANDARDISATION,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.MARKING,
            Action.SUBMIT_FOR_MODERATION,
            State.PENDING_MODERATION,
            "Submit for moderation",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.PENDING_MODERATION,
            Action.COMPLETE_MODERATION,
            moderation_target,
            "Complete moderation",
            relationships=(Relationship.MODERATOR,),
        ),
        _t(
            kind,
            moderation_target,
            Action.APPROVE_MARKS,
            State.MARKS_APPROVED,
            "Approve marks",
            roles=(Role.TEACHING_SUPPORT,),
        ),
    ]


def _coursework() -> list[Transition]:
    kind = Kind.COURSEWORK
    return [
        *_SETTING(kind),
        _t(
            kind,
            State.PENDING_CHECK,
            Action.APPROVE,
            State.CHECK_APPROVED,
            "Approve specification",
            relationships=(Relationship.CHECKER,),
        ),
        _t(
            kind,
            State.CHECK_APPROVED,
            Action.RELEASE,
            State.RELEASED,
            "Release to students",
            roles=(Role.TEACHING_SUPPORT,),
        ),
        _t(
            kind,
            State.RELEASED,
            Action.DEADLINE_PASSED,
            State.DEADLINE_PASSED,
            "Mark the deadline as passed",
            roles=(Role.TEACHING_SUPPORT,),
            guards=(DEADLINE_REACHED,),
        ),
        *_marking(kind, State.DEADLINE_PASSED, State.RESULTS_RETURNED),
    ]


def _test() -> list[Transition]:
    kind = Kind.TEST
    return [
        *_SETTING(kind),
        _t(
            kind,
            State.PENDING_CHECK,
            Action.APPROVE,
            State.CHECK_APPROVED,
            "Approve test",
            relationships=(Relationship.CHECKER,),
        ),
        _t(
            kind,
            State.CHECK_APPROVED,
            Action.RELEASE,
            State.RELEASED,
            "Release to students",
            roles=(Role.TEACHING_SUPPORT,),
        ),
        _t(
            kind,
            State.RELEASED,
            Action.DEADLINE_PASSED,
            State.DEADLINE_PASSED,
            "Mark the test as sat",
            roles=(Role.TEACHING_SUPPORT,),
            guards=(DEADLINE_REACHED,),
        ),
        _t(
            kind,
            State.DEADLINE_PASSED,
            Action.RETURN_RESULTS,
            State.RESULTS_RETURNED,
            "Return autograded results",
            roles=(Role.TEACHING_SUPPORT,),
            guards=(AUTOGRADED,),
        ),
        _t(
            kind,
            State.DEADLINE_PASSED,
            Action.START_STANDARDISATION,
            State.STANDARDISATION,
            "Start marking standardisation",
            relationships=(Relationship.SETTER,),
            roles=(Role.TEACHING_SUPPORT,),
            guards=(MARKED_BY_HAND, MARKED_BY_TEAM),
        ),
        _t(
            kind,
            State.DEADLINE_PASSED,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
            guards=(MARKED_BY_HAND, MARKED_ALONE),
        ),
        _t(
            kind,
            State.STANDARDISATION,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.MARKING,
            Action.SUBMIT_FOR_MODERATION,
            State.PENDING_MODERATION,
            "Submit for moderation",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.PENDING_MODERATION,
            Action.COMPLETE_MODERATION,
            State.RESULTS_RETURNED,
            "Complete moderation",
            relationships=(Relationship.MODERATOR,),
        ),
        _t(
            kind,
            State.RESULTS_RETURNED,
            Action.APPROVE_MARKS,
            State.MARKS_APPROVED,
            "Approve marks",
            roles=(Role.TEACHING_SUPPORT,),
        ),
    ]


def _exam() -> list[Transition]:
    kind = Kind.EXAM
    return [
        *_SETTING(kind),
        _t(
            kind,
            State.PENDING_CHECK,
            Action.APPROVE,
            State.PENDING_EXAM_OFFICER,
            "Approve paper",
            relationships=(Relationship.CHECKER,),
        ),
        _t(
            kind,
            State.PENDING_EXAM_OFFICER,
            Action.APPROVE,
            State.PENDING_EXTERNAL_EXAMINER,
            "Approve paper",
            relationships=(Relationship.EXAM_OFFICER_OF_RECORD,),
        ),
        _t(
            kind,
            State.PENDING_EXAM_OFFICER,
            Action.REQUEST_CHANGES,
            State.EXAM_OFFICER_CHANGES_REQUESTED,
            "Request changes",
            relationships=(Relationship.EXAM_OFFICER_OF_RECORD,),
        ),
        _t(
            kind,
            State.EXAM_OFFICER_CHANGES_REQUESTED,
            Action.RESUBMIT,
            State.PENDING_EXAM_OFFICER,
            "Resubmit to the exam officer",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.PENDING_EXTERNAL_EXAMINER,
            Action.SUBMIT_FEEDBACK,
            State.PENDING_SETTER_RESPONSE,
            "Submit feedback",
            relationships=(Relationship.EXTERNAL_EXAMINER_OF_RECORD,),
        ),
        _t(
            kind,
            State.PENDING_SETTER_RESPONSE,
            Action.SUBMIT_RESPONSE,
            State.PENDING_FINAL_CHECK,
            "Respond to the external examiner",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.PENDING_FINAL_CHECK,
            Action.SEND_TO_PRINT,
            State.SENT_TO_PRINT,
            "Send to print",
            relationships=(Relationship.EXAM_OFFICER_OF_RECORD,),
        ),
        _t(
            kind,
            State.SENT_TO_PRINT,
            Action.DEADLINE_PASSED,
            State.DEADLINE_PASSED,
            "Mark the exam as sat",
            roles=(Role.TEACHING_SUPPORT,),
            guards=(DEADLINE_REACHED,),
        ),
        _t(
            kind,
            State.DEADLINE_PASSED,
            Action.START_STANDARDISATION,
            State.STANDARDISATION,
            "Start marking standardisation",
            relationships=(Relationship.SETTER,),
            roles=(Role.TEACHING_SUPPORT,),
            guards=(MARKED_BY_TEAM,),
        ),
        _t(
            kind,
            State.DEADLINE_PASSED,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
            guards=(MARKED_ALONE,),
        ),
        _t(
            kind,
            State.STANDARDISATION,
            Action.START_MARKING,
            State.MARKING,
            "Start marking",
            relationships=(Relationship.SETTER,),
        ),
        _t(
            kind,
            State.MARKING,
            Action.ADMIN_CHECK,
            State.ADMIN_CHECK,
            "Administrative check",
            roles=(Role.ADMIN_TEAM,),
        ),
        _t(
            kind,
            State.ADMIN_CHECK,
            Action.SUBMIT_FOR_MODERATION,
            State.PENDING_MODERATION,
            "Submit for moderation",
            roles=(Role.ADMIN_TEAM,),
        ),
        _t(
            kind,
            State.PENDING_MODERATION,
            Action.APPROVE_MARKS,
            State.MARKS_APPROVED,
            "Approve marks",
            relationships=(Relationship.MODERATOR,),
        ),
    ]


POLICY: tuple[Transition, ...] = tuple(_coursework() + _test() + _exam())

_INDEX: dict[tuple[Kind, State, Action], Transition] = {}
for _transition in POLICY:
    _key = (_transition.kind, _transition.source, _transition.action)
    if _key in _INDEX:
        raise AssertionError(f"two transitions share {_key}; the policy is ambiguous")
    _INDEX[_key] = _transition


def find(kind: Kind, source: State, action: Action) -> Transition | None:
    return _INDEX.get((kind, source, action))


def transitions_from(kind: Kind, source: State) -> list[Transition]:
    return [t for t in POLICY if t.kind == kind and t.source == source]


def transitions_for(kind: Kind) -> list[Transition]:
    return [t for t in POLICY if t.kind == kind]


def is_permitted(transition: Transition, actor, assessment) -> bool:
    """Permission is a role the actor holds, or a relationship they have."""
    if transition.roles & actor.roles:
        return True
    return bool(transition.relationships & assessment.relationships(actor))


def failing_guards(transition: Transition, assessment: Assessment, today: date) -> list[Guard]:
    return [guard for guard in transition.guards if not guard.holds(assessment, today)]
