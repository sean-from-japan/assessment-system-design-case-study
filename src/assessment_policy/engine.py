"""The one place a workflow state changes.

Everything the engine needs it reads from the store. The caller supplies an
identifier, an action, and who they are — never a state, never a role, never
a nomination of who the checker is. That is not a convenience: it is the
difference between an authorisation check and a suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .errors import Forbidden, GuardFailed, InvalidTransition
from .model import Action, State
from .policy import Transition, failing_guards, find, is_permitted, transitions_from
from .roles import Actor
from .store import AssessmentStore


@dataclass(frozen=True)
class AvailableAction:
    action: Action
    label: str
    blocked_by: tuple = ()

    @property
    def enabled(self) -> bool:
        return not self.blocked_by


@dataclass(frozen=True)
class Applied:
    assessment_id: int
    action: Action
    previous: State
    current: State

    def __str__(self) -> str:
        return f"assessment {self.assessment_id}: {self.previous} --{self.action}--> {self.current}"


class WorkflowEngine:
    def __init__(self, store: AssessmentStore, clock: Callable[[], date] | None = None) -> None:
        self.store = store
        self.clock = clock or date.today

    def available_actions(self, assessment_id: int, actor: Actor) -> list[AvailableAction]:
        """What this actor may do to this assessment now.

        An action whose guard has not been met is still returned, marked with
        the reason, so the interface can explain the wait instead of hiding
        the button. An action the actor may not perform is not returned at
        all — and, crucially, ``perform`` refuses it too, from this same
        table.
        """
        assessment = self.store.get(assessment_id)
        today = self.clock()
        offered: list[AvailableAction] = []
        for transition in transitions_from(assessment.kind, assessment.state):
            if not is_permitted(transition, actor, assessment):
                continue
            blocked = tuple(
                guard.explanation for guard in failing_guards(transition, assessment, today)
            )
            offered.append(AvailableAction(transition.action, transition.label, blocked))
        return sorted(offered, key=lambda item: str(item.action))

    def perform(self, assessment_id: int, actor: Actor, action: Action) -> Applied:
        """Apply an action, or refuse it with a reason that says which check failed."""
        assessment = self.store.get(assessment_id)
        transition = find(assessment.kind, assessment.state, action)
        if transition is None:
            raise InvalidTransition(
                f"{assessment.kind} in state {assessment.state} has no action {action}"
            )
        if not is_permitted(transition, actor, assessment):
            raise Forbidden(
                f"{actor} may not {action} this {assessment.kind}: "
                f"that requires {transition.principals()}"
            )
        blocked = failing_guards(transition, assessment, self.clock())
        if blocked:
            raise GuardFailed("; ".join(guard.explanation for guard in blocked))

        previous = assessment.state
        assessment.state = transition.target
        self.store.save(assessment)
        return Applied(assessment.id, action, previous, transition.target)

    def may(self, assessment_id: int, actor: Actor, action: Action) -> bool:
        """Would ``perform`` succeed? Answered from the same table it uses."""
        assessment = self.store.get(assessment_id)
        transition: Transition | None = find(assessment.kind, assessment.state, action)
        if transition is None or not is_permitted(transition, actor, assessment):
            return False
        return not failing_guards(transition, assessment, self.clock())
