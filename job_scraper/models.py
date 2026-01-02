"""Domain models for jobs, job details, and networking profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class JobSummary:
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    is_viewed: bool = False
    viewed_indicator: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "is_viewed": self.is_viewed,
            "viewed_indicator": self.viewed_indicator,
            "job_url": self.job_url,
        }


@dataclass
class JobDetails:
    job_id: str
    job_url: str
    description: str = ""
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    job_function: Optional[str] = None
    industries: Optional[str] = None
    posted_time: Optional[str] = None
    applicant_count: Optional[int] = None
    remote_eligible: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_url": self.job_url,
            "description": self.description,
            "seniority": self.seniority,
            "employment_type": self.employment_type,
            "job_function": self.job_function,
            "industries": self.industries,
            "posted_time": self.posted_time,
            "applicant_count": self.applicant_count,
            "remote_eligible": self.remote_eligible,
        }


@dataclass
class ProfileCard:
    name: str
    title: str
    profile_url: str
    company: str = ""
    role: str = ""
    connection_status: str = ""
    is_role_match: bool = False
    message_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "profile_url": self.profile_url,
            "company": self.company,
            "role": self.role,
            "connection_status": self.connection_status,
            "is_role_match": self.is_role_match,
            "message_available": self.message_available,
        }
