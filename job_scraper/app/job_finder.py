"""
Main CLI application for LinkedIn job scraping with LLM matching
and Windows toast notifications.

This script provides a command-line interface (CLI) for scraping LinkedIn jobs, scoring them using LLMs, and sending notifications. It includes:
- JobFinder class: Main logic for scraping, scoring, and notification
- CLI commands: scrape, show_jobs, stats, export, loop
"""

# Standard library imports
import logging  # For logging messages to file and console
import sys  # For system-specific parameters and functions
import time  # For time-related functions
from datetime import datetime  # For date and time operations
from pathlib import Path  # For filesystem path operations

# Third-party imports
import click  # For CLI commands and options

# Project-specific imports
from config.config import DATA_DIR, LOG_DIR, Config  # Configuration and paths
from matching.match_scorer import MatchScorer  # LLM-based job matching
from matching.resume_loader import ResumeLoader  # Loads resume text
from openai import OpenAI  # OpenAI API client
from scraping.linkedin_scraper import LinkedInScraper  # LinkedIn scraping logic
from storage_pkg import JobStorage  # Job storage and CSV export
from tabulate import tabulate  # For pretty-printing tables in CLI

# Add project root to sys.path for module imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Setup logging handlers for daily rotation

# Create a log file with today's date (YYYY-MM-DD) if it doesn't exist
today_str = datetime.now().strftime("%Y-%m-%d")
dated_log_filename = f"{LOG_DIR}/job_finder.{today_str}.log"
if not Path(dated_log_filename).exists():
    Path(dated_log_filename).touch()

# Use FileHandler for daily log file
file_handler = logging.FileHandler(dated_log_filename, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# Configure root logger to use both file and console handlers
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

logger = logging.getLogger(__name__)  # Module-level logger


class JobFinder:
    """
    Main job finder application.

    Handles scraping jobs, scoring them with LLM, storing results, and sending notifications.
    Attributes:
        config (Config): Project configuration and settings.
        storage (JobStorage): Handles job storage and CSV export.
        scrapers (list): List of tuples (portal_name, scraper_instance).
        match_threshold (float): Minimum score to consider a job relevant.
        openai_key (str): API key for OpenAI.
        base_model (str): OpenAI model for base scoring.
        rerank_model (str): OpenAI model for reranking.
        rerank_band (float): Score band for reranking.
        openai_client (OpenAI): OpenAI API client instance.
        resume_loader (ResumeLoader): Loads resume text.
        match_scorer (MatchScorer): Scores jobs using LLM.
        resume_text (str): Cached resume text.
    """

    def __init__(self):
        # Load configuration settings
        self.config = Config()  # Loads config from file/env
        # Initialize job storage (writes jobs to CSV)
        self.storage = JobStorage(data_dir=DATA_DIR)
        # List of job portal scrapers (currently LinkedIn only)
        self.scrapers = [
            ("LinkedIn", LinkedInScraper()),
        ]
        # Minimum score to consider a job relevant
        self.match_threshold = self.config.job_match_threshold
        # OpenAI API key and model names
        self.openai_key = self.config.openai_api_key
        self.base_model = self.config.openai_model
        self.rerank_model = self.config.openai_model_rerank
        self.rerank_band = self.config.job_match_rerank_band

        # Initialize OpenAI client safely
        try:
            self.openai_client = (
                OpenAI(api_key=self.openai_key) if self.openai_key else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            self.openai_client = None

        # ResumeLoader loads resume text from file
        self.resume_loader = ResumeLoader(config=self.config, logger=logger)
        # MatchScorer uses LLM to score jobs
        self.match_scorer = MatchScorer(
            config=self.config, openai_client=self.openai_client, logger=logger
        )
        # Cached resume text for scoring
        self.resume_text = self._load_resume_text()

    def _load_resume_text(self) -> str:
        """
        Load resume text using ResumeLoader (full text, cached).
        Returns:
            str: Resume text loaded from file.
        Raises:
            RuntimeError: If resume text is missing or empty.
        """
        text = self.resume_loader.load_text()
        if not text.strip():
            raise RuntimeError(
                f"Resume text not available. Provide RESUME_PATH or place a resume at {self.config.resume_path}."
            )
        return text

    def _score_job_with_llm(self, job: dict, prompt: str = "") -> float:
        """
        Use OpenAI to score job vs resume on 0-10 scale.
        Args:
            job (dict): Job details to score.
            prompt (str): Optional prompt for LLM scoring.
        Returns:
            float: Score from 0.0 to 10.0 indicating match quality.
        """
        if not self.openai_client:
            logger.warning("OPENAI_API_KEY not set; defaulting match score to 0")
            return 0.0
        if not prompt:
            try:
                with open("data/LLM_base_score.txt", "r", encoding="utf-8") as f:
                    prompt = f.read().strip()
            except Exception:
                prompt = 'You are a concise matcher. Score 0-10 (float) how well the candidate fits the job. Consider resume and preferences. If the job title or company is missing/blank, infer them from the description and return them. Return JSON only: {"score": number, "reason": string, "title": string, "company": string}. Keep title/company unchanged if already provided; otherwise, supply concise inferred values.'
        try:
            result = self.match_scorer.score(
                resume_text=self.resume_text,
                job_details=job,
                base_prompt=prompt,
            )
            # Attach LLM scoring details to job dict
            job["match_reason"] = result.get("reason", "")
            if result.get("reranked"):
                job["match_reason_rerank"] = result.get("reason_rerank", "")
                job["match_model_used_rerank"] = result.get("model_used_rerank")
            job["match_model_used"] = result.get("model_used")
            job["reranked"] = result.get("reranked", False)
            job["first_score"] = result.get("first_score", result.get("score", 0.0))
            job["match_reason_first"] = result.get("reason_first", "")
            # Always use LLM-inferred title/company unless empty string.
            inferred_title = (result.get("inferred_title") or "").strip()
            inferred_company = (result.get("inferred_company") or "").strip()
            if inferred_title:
                job["title"] = inferred_title
            if inferred_company:
                job["company"] = inferred_company
            return float(result.get("score", 0.0))
        except Exception as exc:
            logger.error(f"LLM scoring failed: {exc}")
            return 0.0

    def _normalize_job(self, portal_name: str, job: dict) -> dict:
        """
        Normalize job dictionary for storage/export.
        Args:
            portal_name (str): Name of job portal.
            job (dict): Raw job data.
        Returns:
            dict: Normalized job data for CSV/database.
        """
        return {
            "Title": job.get("title", ""),
            "Company": job.get("company", ""),
            "URL": job.get("url", ""),
            "Applicants": job.get("applicant_count", job.get("applicants", 0)),
            "Match Score": job.get("match_score", ""),
        }

    def _notify_job(self, job: dict):
        """
        Log job notification info.
        Args:
            job (dict): Job data to notify/log.
        """
        message = f"{job.get('title', '')} @ {job.get('company', '')} ({job.get('location', '')})"
        logger.info(f"Notify: {message}")

    def _process_jobs(self, portal_name: str, jobs: list, scraper=None) -> list:
        """
        Score, filter, store, find people, and notify for each job.
        Args:
            portal_name (str): Name of job portal.
            jobs (list): List of job dicts.
            scraper: Scraper instance (optional).
        Returns:
            list: List of matched jobs.
        """
        matched = []
        # Import here to avoid circular imports

        from networking.people_finder import PeopleFinder
        from notifications.email_notifier import EmailNotifier

        # Use the active Selenium driver and WebDriverWait from the scraper
        driver = getattr(scraper, "driver", None)
        wait = getattr(scraper, "wait", None)
        email_notifier = EmailNotifier()

        for job in jobs:
            score = self._score_job_with_llm(job)
            job["match_score"] = score
            if score < self.match_threshold:
                logger.info(
                    f"    ❌ Skipped (LLM score {score:.1f} < {self.match_threshold}): {job.get('title', '')} at {job.get('company', '')}"
                )
                continue

            normalized = self._normalize_job(portal_name, job)
            if self.storage.add_job(normalized):
                matched.append(job)
                self._notify_job(job)

                profiles = []
                role = job.get("title", "")
                company = job.get("company", "")
                if driver is not None and wait is not None:
                    try:
                        from networking.people_finder import PeopleFinder

                        people_finder = PeopleFinder(driver, wait, logger)
                        profiles = people_finder.scrape_people_cards(role, company)
                        # LLM only returns matched profiles, so use as-is
                        self.storage.add_people_profiles(
                            profiles, searched_job_title=role
                        )
                    except Exception as pf_exc:
                        logger.error(
                            f"Error scraping or storing LinkedIn profiles for networking: {pf_exc}"
                        )
                else:
                    logger.warning(
                        "PeopleFinder not initialized: driver or wait not available."
                    )

                # Send notification after job and people info are stored
                try:
                    email_notifier.send_job_notification(job, match_profiles=profiles)
                except Exception as en_exc:
                    logger.error(f"Error sending notifications: {en_exc}")
        return matched

    def scrape_single_portal(self, portal_name, max_applicants=100):
        """
        Scrape a single job portal: Scrape → Find People → Export → Notify
        Args:
            portal_name (str): Name of portal to scrape.
            max_applicants (int): Max applicants filter.
        """
        click.echo(click.style(f"\n🔍 Scraping {portal_name}...", fg="cyan", bold=True))
        click.echo("Workflow: Scrape → Filter → Find People → Export to CSV → Notify")
        click.echo("=" * 80)

        # Find the matching scraper
        scraper = None
        for portal, s in self.scrapers:
            if portal == portal_name:
                scraper = s
                break

        if not scraper:
            click.secho(f"❌ Portal '{portal_name}' not found", fg="red")
            click.echo(f"Available portals: {', '.join([p for p, _ in self.scrapers])}")
            return

        try:
            # Phase 1: Scrape portal
            click.echo(f"  Scraping {portal_name}...")
            jobs = scraper.scrape(
                max_applicants=max_applicants,
                scorer=self._score_job_with_llm,
                match_threshold=self.match_threshold,
                storage=self.storage,
                connect_pages=self.config.max_people_search_pages,
                connect_delay_range=(
                    self.config.request_delay_min,
                    self.config.request_delay_max,
                ),
            )
            click.echo(f"  ✅ Completed {len(jobs)} job evaluations for {portal_name}")

            click.secho(f"  ✨ {portal_name} workflow complete", fg="green")
            click.echo("=" * 80)

        except Exception as e:
            click.secho(f"  ❌ Error processing {portal_name}: {str(e)}", fg="red")
            logger.error(f"Error scraping {portal_name}: {str(e)}")

    def scrape_jobs(self, max_applicants: int | None = None):
        """
        Scrape LinkedIn: Scrape → Find People → Export → Notify
        Args:
            max_applicants (int | None): Max applicants filter.
        Returns:
            list: All jobs scraped and processed.
        """
        max_applicants = max_applicants or self.config.max_applicants
        click.echo(
            click.style("\n🔍 Starting LinkedIn job scraper...", fg="cyan", bold=True)
        )
        click.echo("Workflow: Scrape → Filter → Find People → Export to CSV → Notify")
        click.echo("=" * 80)

        # Only LinkedIn scraper is used
        portal_name, scraper = self.scrapers[0]
        all_jobs = []
        try:
            click.echo(
                click.style(f"\n🚀 Processing {portal_name}...", fg="cyan", bold=True)
            )
            click.echo(f"  Scraping {portal_name}...")
            jobs = scraper.scrape(
                max_applicants=max_applicants,
                scorer=self._score_job_with_llm,
                match_threshold=self.match_threshold,
                storage=self.storage,
                connect_pages=self.config.max_people_search_pages,
                connect_delay_range=(
                    self.config.request_delay_min,
                    self.config.request_delay_max,
                ),
            )
            click.echo(f"  ✅ Completed {len(jobs)} job evaluations for {portal_name}")
            click.secho(f"  ✨ {portal_name} workflow complete", fg="green")
            all_jobs.extend(jobs)
        except Exception as e:
            click.secho(f"  ❌ Error processing {portal_name}: {str(e)}", fg="red")
            logger.error(f"Error scraping {portal_name}: {str(e)}")

        click.echo("\n" + "=" * 80)
        click.secho(
            f"✅ LinkedIn scrape finished. Total jobs scraped: {len(all_jobs)}",
            fg="green",
            bold=True,
        )
        return all_jobs

    def show_new_jobs(self, hours=24):
        """
        Display new jobs from last N hours.
        Args:
            hours (int): Number of hours to look back for new jobs.
        """
        jobs = self.storage.get_all_jobs()

        if not jobs:
            click.echo("❌ No jobs found")
            return

        click.echo(f"\n📋 {len(jobs)} Relevant Jobs in Database:")
        click.echo("=" * 80)

        table_data = []
        for i, job in enumerate(jobs, 1):
            table_data.append(
                [
                    i,
                    job.get("Title", "")[:20],
                    job.get("Company", "")[:15],
                    job.get("URL", "")[:30],
                    job.get("Applicants", ""),
                    job.get("Match Score", ""),
                ]
            )

        headers = ["#", "Title", "Company", "URL", "Applicants", "Match Score"]
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Show CSV location
        click.secho("\n📁 Jobs stored in: data/jobs.csv", fg="green")
        if Path("data/jobs.csv").exists():
            click.secho("📊 CSV file available: data/jobs.csv", fg="green")

    # --- Simplified continuous loop runner ---
    def run_loop(self, interval_minutes=15, max_applicants=100):
        """
        Continuously run all portal workflows with a sleep between cycles.
        Args:
            interval_minutes (int): Minutes between each scrape cycle.
            max_applicants (int): Max applicants filter for jobs.
        """
        click.echo(
            click.style(
                f"\n▶️  Continuous loop every {interval_minutes} minutes (Ctrl+C to stop)",
                fg="cyan",
                bold=True,
            )
        )
        while True:
            cycle_start = time.time()
            try:
                self.scrape_jobs(max_applicants=max_applicants)
            except Exception as exc:
                logger.error(f"Loop cycle error: {exc}")
            elapsed = time.time() - cycle_start
            sleep_seconds = max(interval_minutes * 60 - elapsed, 0)
            click.echo(
                f"⏳ Sleeping {sleep_seconds / 60:.1f} minutes before next cycle..."
            )
            time.sleep(sleep_seconds)


@click.group()
def cli():
    """
    Job Scraper CLI - Find jobs and automate LinkedIn outreach.
    This is the main entry point for CLI commands.
    """
    pass


@cli.command()
@click.option(
    "--max-applicants",
    default=None,
    type=int,
    help="Max applicants threshold (defaults to MAX_APPLICANTS from .env)",
)
def scrape(max_applicants):
    """
    Scrape LinkedIn for relevant positions.
    Args:
        max_applicants (int): Max applicants filter for jobs.
    """
    finder = JobFinder()
    finder.scrape_jobs(max_applicants=max_applicants)


@cli.command()
@click.option("--hours", default=24, help="Show jobs from last N hours")
def show_jobs(hours):
    """
    Show recent jobs from database.
    Args:
        hours (int): Number of hours to look back for jobs.
    """
    finder = JobFinder()
    finder.show_new_jobs(hours=hours)


@cli.command()
def stats():
    """
    Show job statistics.
    Displays statistics about jobs scraped and stored.
    """
    finder = JobFinder()
    stats_data = finder.storage.get_stats()

    click.echo(click.style("\n📊 Job Scraper Statistics", fg="cyan", bold=True))
    click.echo("=" * 50)
    for key, value in stats_data.items():
        key_display = key.replace("_", " ").title()
        click.echo(f"{key_display}: {value}")
    click.echo("=" * 50)


@cli.command()
def export():
    """
    Export jobs to CSV (already automatic).
    This command is informational; jobs are exported automatically.
    """
    click.echo("\n📊 Jobs are automatically exported to CSV...")
    click.secho("✅ Jobs are automatically saved to data/jobs.csv", fg="green")


@cli.command()
@click.option("--interval", default=1, help="Minutes between scrapes (default: 15)")
@click.option(
    "--max-applicants", default=100, help="Max applicants filter (default: 100)"
)
def loop(interval, max_applicants):
    """
    Run scraper continuously in a loop.
    Args:
        interval (int): Minutes between scrapes.
        max_applicants (int): Max applicants filter for jobs.
    """
    finder = JobFinder()
    iteration = 1

    click.echo(
        click.style("\n🔄 Starting continuous scraper loop", fg="cyan", bold=True)
    )
    click.echo(f"⏱️  Will run every {interval} minutes")
    click.echo(f"👥 Max applicants filter: {max_applicants}")
    click.echo("Press Ctrl+C to stop")
    click.echo("=" * 80)

    try:
        while True:
            click.echo(click.style(f"\n\n{'=' * 80}", fg="yellow"))
            click.echo(
                click.style(
                    f"🔄 ITERATION #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    fg="yellow",
                    bold=True,
                )
            )
            click.echo(click.style(f"{'=' * 80}\n", fg="yellow"))

            try:
                finder.scrape_jobs(max_applicants=max_applicants)
            except Exception as e:
                click.secho(f"❌ Error in iteration {iteration}: {str(e)}", fg="red")
                logger.error(f"Loop iteration {iteration} error: {str(e)}")

            iteration += 1

            # Wait for next iteration
            wait_seconds = interval * 60
            click.echo(f"\n⏸️  Waiting {interval} minutes until next scrape...")
            time.sleep(wait_seconds)

    except KeyboardInterrupt:
        click.echo(
            click.style("\n\n⛔ Scraper stopped by user", fg="yellow", bold=True)
        )
        click.echo(f"Completed {iteration - 1} iterations")


if __name__ == "__main__":
    # Entry point for CLI execution
    cli()
