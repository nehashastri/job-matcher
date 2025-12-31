"""Storage package for matched jobs and blocklist.

Exports JobStorage (alias of MatchedJobsStore) for compatibility with legacy imports.
"""

from .matched_jobs_store import MatchedJobsStore
from .matched_jobs_store import MatchedJobsStore as JobStorage

__all__ = ["MatchedJobsStore", "JobStorage"]
