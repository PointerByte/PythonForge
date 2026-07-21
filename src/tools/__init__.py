"""Background work: scheduled jobs and bounded worker pools.

Both are lifecycle-owned -- hand them to ``create_app``'s ``on_startup`` /
``on_shutdown`` hooks or to ``ServiceRuntime`` so nothing outlives the
process that created it.
"""

from .jobs import CronSchedule, Job, JobScheduler, JobState, JobStats
from .workers import WorkerPool, WorkerStats

__all__ = [
    "CronSchedule",
    "Job",
    "JobScheduler",
    "JobState",
    "JobStats",
    "WorkerPool",
    "WorkerStats",
]
