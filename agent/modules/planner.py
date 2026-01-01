from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class Importance(Enum):
    HIGH = "hoch"
    LOW = "niedrig"


class Urgency(Enum):
    HIGH = "hoch"
    LOW = "niedrig"


@dataclass
class Task:
    name: str
    importance: Importance
    urgency: Urgency


@dataclass
class PrioritizedTasks:
    do_now: List[Task]          # wichtig + dringend
    schedule: List[Task]        # wichtig + nicht dringend
    delegate: List[Task]        # nicht wichtig + dringend
    delete: List[Task]          # nicht wichtig + nicht dringend


def prioritize(tasks: List[Task]) -> PrioritizedTasks:
    """Sort tasks into Eisenhower categories."""
    do_now: List[Task] = []
    schedule: List[Task] = []
    delegate: List[Task] = []
    delete: List[Task] = []

    for t in tasks:
        if t.importance is Importance.HIGH and t.urgency is Urgency.HIGH:
            do_now.append(t)
        elif t.importance is Importance.HIGH and t.urgency is Urgency.LOW:
            schedule.append(t)
        elif t.importance is Importance.LOW and t.urgency is Urgency.HIGH:
            delegate.append(t)
        else:
            delete.append(t)

    # Optional: within each group keep original order
    return PrioritizedTasks(
        do_now=do_now,
        schedule=schedule,
        delegate=delegate,
        delete=delete,
    )
