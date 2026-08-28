"""Where assessments live. In-memory here; the interface is the point."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import NotFound
from .model import Assessment


class AssessmentStore:
    def __init__(self, assessments: Iterable[Assessment] = ()) -> None:
        self._items: dict[int, Assessment] = {item.id: item for item in assessments}

    def add(self, assessment: Assessment) -> Assessment:
        if assessment.id in self._items:
            raise ValueError(f"assessment {assessment.id} already exists")
        self._items[assessment.id] = assessment
        return assessment

    def get(self, assessment_id: int) -> Assessment:
        try:
            return self._items[assessment_id]
        except KeyError:
            raise NotFound(f"no assessment with id {assessment_id}") from None

    def save(self, assessment: Assessment) -> Assessment:
        self._items[assessment.id] = assessment
        return assessment

    def all(self) -> list[Assessment]:
        return list(self._items.values())
