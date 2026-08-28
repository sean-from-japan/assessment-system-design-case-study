"""Failures that callers are expected to handle, kept distinct on purpose.

Collapsing "you may not" into "that is not possible" is how an authorisation
bug becomes invisible: the caller sees a refusal either way, and the log
cannot tell you which one happened.
"""

from __future__ import annotations


class WorkflowError(Exception):
    """Base class for every refusal this engine issues."""


class NotFound(WorkflowError):
    """No assessment with that identifier."""


class Forbidden(WorkflowError):
    """The transition exists, but this actor may not perform it."""


class InvalidTransition(WorkflowError):
    """No transition leaves this state under this action, for anyone."""


class GuardFailed(WorkflowError):
    """The actor is permitted and the transition exists, but a precondition
    of the domain is not met yet."""
