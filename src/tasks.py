"""Celery tasks for Decision Analyzer."""

from src.celery_app import celery_app


@celery_app.task
def periodic_reanalysis():
    """Periodic task to re-analyze ADRs based on external data."""
    from src.reanalysis_automation import ReanalysisAutomationService
    from src.web_search import WebSearchService
    from src.job_scheduler import JobScheduler

    try:
        # Initialize services
        web_search = WebSearchService()
        reanalysis_service = ReanalysisAutomationService(web_search)
        job_scheduler = JobScheduler()

        # Run periodic re-analysis
        # This would typically scan for ADRs that need re-analysis
        # For now, just log that the task ran
        return {"status": "completed", "message": "Periodic re-analysis completed"}

    except Exception as e:
        return {"status": "failed", "error": str(e)}
