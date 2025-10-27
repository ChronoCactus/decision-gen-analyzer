"""Job scheduling system for periodic ADR re-analysis."""

import asyncio
import json
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID, uuid4

import structlog

from config import Settings


logger = structlog.get_logger(__name__)


class JobStatus(str, Enum):
    """Status of a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Types of scheduled jobs."""
    ADR_REANALYSIS = "adr_reanalysis"
    WEB_SEARCH_UPDATE = "web_search_update"
    CONTINUITY_CHECK = "continuity_check"
    CONFLICT_DETECTION = "conflict_detection"


class ScheduledJob:
    """Represents a scheduled job."""

    def __init__(
        self,
        job_type: JobType,
        job_id: Optional[str] = None,
        schedule_interval: Optional[int] = None,  # seconds
        next_run: Optional[datetime] = None,
        last_run: Optional[datetime] = None,
        status: JobStatus = JobStatus.PENDING,
        parameters: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_count: int = 0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.job_id = job_id or str(uuid4())
        self.job_type = job_type
        self.schedule_interval = schedule_interval
        self.next_run = next_run or datetime.now(UTC)
        self.last_run = last_run
        self.status = status
        self.parameters = parameters or {}
        self.max_retries = max_retries
        self.retry_count = retry_count
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "schedule_interval": self.schedule_interval,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "status": self.status.value,
            "parameters": self.parameters,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledJob":
        """Create from dictionary."""
        return cls(
            job_id=data["job_id"],
            job_type=JobType(data["job_type"]),
            schedule_interval=data.get("schedule_interval"),
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            status=JobStatus(data["status"]),
            parameters=data.get("parameters", {}),
            max_retries=data.get("max_retries", 3),
            retry_count=data.get("retry_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def should_run(self) -> bool:
        """Check if job should run now."""
        return (
            self.status in [JobStatus.PENDING, JobStatus.COMPLETED, JobStatus.FAILED] and
            self.next_run and
            datetime.now(UTC) >= self.next_run
        )

    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.last_run = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def mark_completed(self) -> None:
        """Mark job as completed and schedule next run."""
        self.status = JobStatus.COMPLETED
        self.retry_count = 0
        self.updated_at = datetime.now(UTC)

        if self.schedule_interval:
            self.next_run = datetime.now(UTC) + timedelta(seconds=self.schedule_interval)

    def mark_failed(self, error: Optional[str] = None) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.updated_at = datetime.now(UTC)

        if self.retry_count < self.max_retries:
            # Schedule retry with exponential backoff
            delay = 60 * (2 ** self.retry_count)  # 1min, 2min, 4min
            self.next_run = datetime.now(UTC) + timedelta(seconds=delay)
            self.retry_count += 1
            self.status = JobStatus.PENDING
        else:
            logger.error(
                "Job failed permanently after max retries",
                job_id=self.job_id,
                job_type=self.job_type.value,
                retry_count=self.retry_count,
                error=error,
            )


class JobScheduler:
    """Scheduler for managing periodic jobs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs: Dict[str, ScheduledJob] = {}
        self.job_handlers: Dict[JobType, Callable] = {}
        self.running = False
        self.check_interval = settings.job_check_interval
        self.max_concurrent_jobs = settings.max_concurrent_jobs
        self.logger = structlog.get_logger(__name__)

    def register_handler(self, job_type: JobType, handler: Callable) -> None:
        """Register a handler function for a job type."""
        self.job_handlers[job_type] = handler
        self.logger.info(
            "Registered job handler",
            job_type=job_type.value,
            handler=handler.__name__,
        )

    def add_job(
        self,
        job_type: JobType,
        schedule_interval: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        run_immediately: bool = False,
    ) -> str:
        """Add a new scheduled job."""
        job = ScheduledJob(
            job_type=job_type,
            schedule_interval=schedule_interval,
            parameters=parameters or {},
            next_run=datetime.now(UTC) if run_immediately else None,
        )

        self.jobs[job.job_id] = job

        self.logger.info(
            "Added scheduled job",
            job_id=job.job_id,
            job_type=job_type.value,
            schedule_interval=schedule_interval,
            run_immediately=run_immediately,
        )

        return job.job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.logger.info("Removed scheduled job", job_id=job_id)
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(
        self,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
    ) -> List[ScheduledJob]:
        """List jobs with optional filtering."""
        jobs = list(self.jobs.values())

        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]

        if status:
            jobs = [j for j in jobs if j.status == status]

        return jobs

    async def start(self) -> None:
        """Start the job scheduler."""
        self.running = True
        self.logger.info("Job scheduler started")

        while self.running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(
                    "Error in job scheduler loop",
                    error=str(e),
                )
                await asyncio.sleep(60)  # Wait a minute before retrying

    def stop(self) -> None:
        """Stop the job scheduler."""
        self.running = False
        self.logger.info("Job scheduler stopped")

    async def _check_and_run_jobs(self) -> None:
        """Check for jobs that should run and execute them."""
        # Find jobs that should run
        jobs_to_run = [job for job in self.jobs.values() if job.should_run()]

        if not jobs_to_run:
            return

        # Limit concurrent jobs
        jobs_to_run = jobs_to_run[:self.max_concurrent_jobs]

        # Run jobs concurrently
        tasks = []
        for job in jobs_to_run:
            task = asyncio.create_task(self._run_job(job))
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_job(self, job: ScheduledJob) -> None:
        """Run a single job."""
        job.mark_running()

        try:
            handler = self.job_handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job.job_type}")

            self.logger.info(
                "Running scheduled job",
                job_id=job.job_id,
                job_type=job.job_type.value,
            )

            # Run the handler
            result = await handler(job.parameters)

            job.mark_completed()

            self.logger.info(
                "Job completed successfully",
                job_id=job.job_id,
                job_type=job.job_type.value,
                result=result,
            )

        except Exception as e:
            error_msg = str(e)
            job.mark_failed(error_msg)

            self.logger.error(
                "Job failed",
                job_id=job.job_id,
                job_type=job.job_type.value,
                error=error_msg,
            )

    def save_state(self, filepath: str) -> None:
        """Save scheduler state to file."""
        state = {
            "jobs": {job_id: job.to_dict() for job_id, job in self.jobs.items()},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            self.logger.info("Scheduler state saved", filepath=filepath)
        except Exception as e:
            self.logger.error(
                "Failed to save scheduler state",
                filepath=filepath,
                error=str(e),
            )

    def load_state(self, filepath: str) -> None:
        """Load scheduler state from file."""
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)

            self.jobs = {}
            for job_id, job_data in state.get("jobs", {}).items():
                self.jobs[job_id] = ScheduledJob.from_dict(job_data)

            self.logger.info(
                "Scheduler state loaded",
                filepath=filepath,
                jobs_loaded=len(self.jobs),
            )
        except FileNotFoundError:
            self.logger.info("No scheduler state file found, starting fresh", filepath=filepath)
        except Exception as e:
            self.logger.error(
                "Failed to load scheduler state",
                filepath=filepath,
                error=str(e),
            )


class NotificationManager:
    """Manager for sending notifications about job results and ADR changes."""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.notifications: List[Dict[str, Any]] = []

    def add_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a notification."""
        notification_id = str(uuid4())

        notification = {
            "id": notification_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        self.notifications.append(notification)

        self.logger.info(
            "Notification added",
            notification_id=notification_id,
            type=notification_type,
            severity=severity,
        )

        return notification_id

    def get_notifications(
        self,
        notification_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get notifications with optional filtering."""
        notifications = self.notifications

        if notification_type:
            notifications = [n for n in notifications if n["type"] == notification_type]

        if severity:
            notifications = [n for n in notifications if n["severity"] == severity]

        # Return most recent first
        return notifications[-limit:]

    def clear_notifications(self, older_than_days: int = 30) -> int:
        """Clear old notifications."""
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

        original_count = len(self.notifications)
        self.notifications = [
            n for n in self.notifications
            if datetime.fromisoformat(n["timestamp"]) > cutoff
        ]

        cleared_count = original_count - len(self.notifications)

        if cleared_count > 0:
            self.logger.info(
                "Cleared old notifications",
                cleared_count=cleared_count,
                remaining=len(self.notifications),
            )

        return cleared_count

    def notify_adr_change(
        self,
        adr_id: str,
        change_type: str,
        description: str,
        confidence: float,
    ) -> str:
        """Notify about ADR changes detected during re-analysis."""
        severity = "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low"

        return self.add_notification(
            notification_type="adr_change",
            title=f"ADR Change Detected: {change_type}",
            message=description,
            severity=severity,
            metadata={
                "adr_id": adr_id,
                "change_type": change_type,
                "confidence": confidence,
            },
        )

    def notify_job_failure(
        self,
        job_id: str,
        job_type: str,
        error: str,
    ) -> str:
        """Notify about job failures."""
        return self.add_notification(
            notification_type="job_failure",
            title=f"Job Failed: {job_type}",
            message=f"Job {job_id} failed: {error}",
            severity="high",
            metadata={
                "job_id": job_id,
                "job_type": job_type,
                "error": error,
            },
        )

    def notify_reanalysis_complete(
        self,
        adr_count: int,
        changes_found: int,
    ) -> str:
        """Notify about completed re-analysis."""
        severity = "medium" if changes_found > 0 else "low"

        return self.add_notification(
            notification_type="reanalysis_complete",
            title="ADR Re-analysis Complete",
            message=f"Analyzed {adr_count} ADRs, found {changes_found} potential changes",
            severity=severity,
            metadata={
                "adr_count": adr_count,
                "changes_found": changes_found,
            },
        )
