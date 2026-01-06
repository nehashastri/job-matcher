"""
Main CLI application for LinkedIn job scraping with LLM matching
and Windows toast notifications
"""

# All imports at the top
import logging
import sys
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import click
from config.config import DATA_DIR, LOG_DIR, Config
from matching.match_scorer import MatchScorer
from matching.resume_loader import ResumeLoader
from openai import OpenAI
from scraping.linkedin_scraper import LinkedInScraper
from storage_pkg import JobStorage
from tabulate import tabulate

# Add project root to path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Setup logging handlers for daily rotation
log_filename = f"{LOG_DIR}/job_finder.log"
file_handler = TimedRotatingFileHandler(
    log_filename, when="midnight", interval=1, backupCount=7, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

logger = logging.getLogger(__name__)


class JobFinder:
    """Main job finder application"""

    def __init__(self):
        self.config = Config()
        self.storage = JobStorage(data_dir=DATA_DIR)
        # LinkedIn-only workflow
        self.scrapers = [
            ("LinkedIn", LinkedInScraper()),
        ]
        self.match_threshold = self.config.job_match_threshold
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

        self.resume_loader = ResumeLoader(config=self.config, logger=logger)
        self.match_scorer = MatchScorer(
            config=self.config, openai_client=self.openai_client, logger=logger
        )
        self.resume_text = self._load_resume_text()

    def _load_resume_text(self) -> str:
        """Load resume text using ResumeLoader (full text, cached)."""
        text = self.resume_loader.load_text()
        if not text.strip():
            raise RuntimeError(
                f"Resume text not available. Provide RESUME_PATH or place a resume at {self.config.resume_path}."
            )
        return text

    def _score_job_with_llm(self, job: dict, prompt: str = "") -> float:
        """Use OpenAI to score job vs resume on 0-10 scale. Always uses .txt file prompt if not provided."""
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
        return {
            "Title": job.get("title", ""),
            "Company": job.get("company", ""),
            "URL": job.get("url", ""),
            "Applicants": job.get("applicant_count", job.get("applicants", 0)),
            "Match Score": job.get("match_score", ""),
        }

    def _notify_job(self, job: dict):
        """Log job notification info."""
        message = f"{job.get('title', '')} @ {job.get('company', '')} ({job.get('location', '')})"
        logger.info(f"Notify: {message}")

    def _process_jobs(self, portal_name: str, jobs: list, scraper=None) -> list:
        """Score, filter, store, find people, and notify for each job."""
        matched = []
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
                # Jobs are now written to CSV automatically; no export needed.
                self._notify_job(job)
        return matched

    def scrape_single_portal(self, portal_name, max_applicants=100):
        """Scrape a single job portal: Scrape → Find People → Export → Notify"""
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
        """Scrape LinkedIn: Scrape → Find People → Export → Notify"""
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
        """Display new jobs from last N hours"""
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
        """Continuously run all portal workflows with a sleep between cycles."""
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
    """Job Scraper CLI - Find jobs and automate LinkedIn outreach"""
    pass


@cli.command()
@click.option(
    "--max-applicants",
    default=None,
    type=int,
    help="Max applicants threshold (defaults to MAX_APPLICANTS from .env)",
)
def scrape(max_applicants):
    """Scrape LinkedIn for relevant positions"""
    finder = JobFinder()
    finder.scrape_jobs(max_applicants=max_applicants)


@cli.command()
@click.option("--hours", default=24, help="Show jobs from last N hours")
def show_jobs(hours):
    """Show recent jobs from database"""
    finder = JobFinder()
    finder.show_new_jobs(hours=hours)


@cli.command()
def stats():
    """Show job statistics"""
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
    """Export jobs to CSV (already automatic)."""
    click.echo("\n📊 Jobs are automatically exported to CSV...")
    click.secho("✅ Jobs are automatically saved to data/jobs.csv", fg="green")


@cli.command()
@click.option("--interval", default=15, help="Minutes between scrapes (default: 15)")
@click.option(
    "--max-applicants", default=100, help="Max applicants filter (default: 100)"
)
def loop(interval, max_applicants):
    """Run scraper continuously in a loop."""
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
    cli()
