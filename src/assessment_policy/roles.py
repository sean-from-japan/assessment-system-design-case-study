"""Who someone is, and what they are to a particular assessment.

Two different questions, deliberately given two different types.

* A **role** is a standing property of a member of staff.
* A **relationship** is per assessment: the same academic is the setter of one
  paper and the checker of another, and a permission that depends on that
  cannot be answered from the role alone.

Roles are a set, not a delimited string. The system this study examines stored
them as one comma-joined string and tested membership with substring search,
which makes ``ACADEMIC`` match ``EXTERNAL_ACADEMIC`` and makes every new role
name a potential silent privilege change.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    ACADEMIC = "academic"
    TEACHING_SUPPORT = "teaching_support"
    EXAM_OFFICER = "exam_officer"
    EXTERNAL_EXAMINER = "external_examiner"
    ADMIN_TEAM = "admin_team"

    def __str__(self) -> str:
        return self.value


class Relationship(Enum):
    """How an actor stands to one specific assessment."""

    SETTER = "setter"
    CHECKER = "checker"
    MODERATOR = "moderator"
    EXAM_OFFICER_OF_RECORD = "exam_officer_of_record"
    EXTERNAL_EXAMINER_OF_RECORD = "external_examiner_of_record"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Actor:
    """The authenticated caller, as the engine sees them.

    The roles here come from the server's own record of the staff member.
    Nothing in this package accepts a role supplied by the caller.
    """

    staff_id: int
    roles: frozenset[Role]

    def __init__(self, staff_id: int, roles: Iterable[Role]) -> None:
        object.__setattr__(self, "staff_id", staff_id)
        object.__setattr__(self, "roles", frozenset(roles))
        for role in self.roles:
            if not isinstance(role, Role):
                raise TypeError(f"not a Role: {role!r}")

    def has_role(self, role: Role) -> bool:
        return role in self.roles

    def __str__(self) -> str:
        names = ", ".join(sorted(str(role) for role in self.roles)) or "no roles"
        return f"staff {self.staff_id} ({names})"
