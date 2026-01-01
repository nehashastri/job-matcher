"""
Main CLI application for LinkedIn job scraping with LLM matching
and Windows toast notifications
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from openai import OpenAI
from tabulate import tabulate

try:
    from win10toast import ToastNotifier
except ImportError:  # Graceful fallback if toast package missing
    ToastNotifier = None

# Fix UTF-8 encoding on Windows PowerShell
if sys.platform == "win32":
    try:
        # Set UTF-8 encoding for console output
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass  # Fallback if reconfigure fails

# Add project root to path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.config import LOG_DIR, Config  # noqa: E402
from matching.match_scorer import MatchScorer  # noqa: E402
from matching.resume_loader import ResumeLoader  # noqa: E402
from scraping.linkedin_scraper import LinkedInScraper  # noqa: E402
from storage_pkg import JobStorage  # noqa: E402


# Custom formatter that strips emojis for console but keeps them for file
class ConsoleFormatter(logging.Formatter):
    """Formatter that removes emojis for console output"""

    def format(self, record):
        formatted = super().format(record)
        # Remove emoji characters that can't be displayed
        import re

        # Remove emoji patterns
        formatted = re.sub(
            r"[\U0001F300-\U0001F9FF]|[\u2700-\u27BF]|[\u2600-\u26FF]|[\u2300-\u23FF]",
            "",
            formatted,
        )
        return formatted


class FileFormatter(logging.Formatter):
    """Formatter that keeps all content including emojis"""

    pass


# Setup logging handlers
file_handler = logging.FileHandler(f"{LOG_DIR}/job_finder.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    FileFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    ConsoleFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

logger = logging.getLogger(__name__)


class JobFinder:
    """Main job finder application"""

    def __init__(self):
        self.config = Config()
        self.storage = JobStorage(data_dir="data")
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
        self.preferences_text = self._load_preferences()
        self.notifier = ToastNotifier() if ToastNotifier else None

    def _load_resume_text(self) -> str:
        """Load resume text using ResumeLoader (full text, cached)."""
        return self.resume_loader.load_text()

    def _load_preferences(self) -> str:
        """Load preferences text from PREFERENCES_PATH or data/preferences.txt."""
        candidates = [
            os.getenv("PREFERENCES_PATH"),
            os.path.join("data", "preferences.txt"),
        ]
        for path in candidates:
            if not path:
                continue
            p = Path(path)
            if not p.exists():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                logger.info(f"Loaded preferences from {p}")
                return text[:4000]
            except Exception as exc:
                logger.warning(f"Could not read preferences at {p}: {exc}")
        return ""

    def _score_job_with_llm(self, job: dict) -> float:
        """Use OpenAI to score job vs resume/preferences on 0-10 scale."""
        if not self.openai_client:
            logger.warning("OPENAI_API_KEY not set; defaulting match score to 0")
            return 0.0
        try:
            description = job.get("description", "")
            prompt = (
                "You are a concise matcher. Score 0-10 (float) how well the candidate fits the job. "
                'Consider resume and preferences. Return JSON: {"score": number, "reason": string}.'
            )
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Resume:\n{self.resume_text}\n\nPreferences:\n{self.preferences_text}",
                },
                {
                    "role": "user",
                    "content": (
                        f"Job Title: {job.get('title', '')}\n"
                        f"Company: {job.get('company', '')}\n"
                        f"Location: {job.get('location', '')}\n"
                        f"Description: {description[:4000]}"
                    ),
                },
            ]

            result = self.match_scorer.score(
                resume_text=self.resume_text,
                preferences_text=self.preferences_text,
                job_details=job,
            )

            job["match_reason"] = result.get("reason", "")
            if result.get("reranked"):
                job["match_reason_rerank"] = result.get("reason_rerank", "")
                job["match_model_used_rerank"] = result.get("model_used_rerank")
            job["match_model_used"] = result.get("model_used")
            return float(result.get("score", 0.0))
        except Exception as exc:
            logger.error(f"LLM scoring failed: {exc}")
            return 0.0

    def _normalize_job(self, portal_name: str, job: dict) -> dict:
        return {
            "ID": str(job.get("id", hash(job.get("url", job.get("title", ""))))),
            "Title": job.get("title", ""),
            "Company": job.get("company", ""),
            "Location": job.get("location", "Remote"),
            "Job URL": job.get("url", ""),
            "Source": job.get("source", portal_name),
            "Applicants": job.get("applicant_count", job.get("applicants", 0)),
            "Posted Date": job.get("posted_date", ""),
            "Scraped Date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "Match Score": job.get("match_score", ""),
            "Viewed": "No",
            "Saved": "No",
            "Applied": "No",
            "Emailed": "No",
        }

    def _notify_job(self, job: dict):
        """Send local toast notification if available."""
        message = f"{job.get('title', '')} @ {job.get('company', '')} ({job.get('location', '')})"
        if self.notifier:
            try:
                self.notifier.show_toast(
                    "Matched Job", message, duration=5, threaded=True
                )
            except Exception as exc:
                logger.debug(f"Toast notify failed: {exc}")
        logger.info(f"Notify: {message}")

    def _build_connect_message(self, job: dict, name: str) -> str:
        base = self.preferences_text.strip()[:400]
        return (
            f"Hi {name}, I spotted a {job.get('title', '')} role at {job.get('company', '')} and"
            " believe my background is a strong match (AI/ML, data)."
            f" Would love to connect and learn more. {base if base else ''}"
        ).strip()

    def _connect_via_scraper(self, job: dict, scraper, limit: int = 5):
        """Use scraper to find similar people at company and save to Excel."""
        try:
            role = job.get("title", "")
            company = job.get("company", "")

            logger.info(f"🔗 Finding people at {company} for role: {role}")

            # Find similar people using scraper
            people = scraper.find_similar_people_at_company(company, role)

            if people:
                logger.info(f"  Found {len(people)} people at {company}")

                # Store people info
                for person in people[:limit]:
                    try:
                        self.storage.add_linkedin_connection(
                            {
                                "name": person.get("name", ""),
                                "title": person.get("title", ""),
                                "url": person.get("profile_url", ""),
                                "company": company,
                                "role": role,
                                "country": "US",
                                "message_sent": "No",
                                "status": "Identified",
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Could not save person info: {e}")

                logger.info(f"  ✅ Saved {len(people)} people to Excel")
            else:
                logger.debug(f"  No people found for {role} at {company}")
        except Exception as e:
            logger.debug(f"  Error in people search: {e}")

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
                # Find similar people at company
                if scraper and hasattr(scraper, "find_similar_people_at_company"):
                    self._connect_via_scraper(job, scraper)
                # Write to Excel immediately after adding a match
                try:
                    self.storage.export_to_excel()
                except Exception as exc:
                    logger.debug(f"Excel export failed: {exc}")
                self._notify_job(job)
        return matched

    def scrape_single_portal(self, portal_name, max_applicants=100):
        """Scrape a single job portal: Scrape → Find People → Export → Notify"""
        click.echo(click.style(f"\n🔍 Scraping {portal_name}...", fg="cyan", bold=True))
        click.echo("Workflow: Scrape → Filter → Find People → Export to Excel → Notify")
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
                connect_limit=5,
            )
            click.echo(f"  ✅ Completed {len(jobs)} job evaluations for {portal_name}")

            click.secho(f"  ✨ {portal_name} workflow complete", fg="green")
            click.echo("=" * 80)

        except Exception as e:
            click.secho(f"  ❌ Error processing {portal_name}: {str(e)}", fg="red")
            logger.error(f"Error scraping {portal_name}: {str(e)}")

    def scrape_jobs(self, max_applicants=100):
        """Scrape each portal: Scrape → Find People → Export → Notify"""
        click.echo(
            click.style(
                "\n🔍 Starting multi-portal job scraper...", fg="cyan", bold=True
            )
        )
        click.echo(
            "Workflow: Scrape → Filter → Find People → Export to Excel → Notify (per portal)"
        )
        click.echo("=" * 80)

        all_jobs = []

        # Process each scraper in sequence
        for portal_name, scraper in self.scrapers:
            click.echo(
                click.style(f"\n🚀 Processing {portal_name}...", fg="cyan", bold=True)
            )

            try:
                # Phase 1: Scrape portal with inline scoring/connecting
                click.echo(f"  Scraping {portal_name}...")
                jobs = scraper.scrape(
                    max_applicants=max_applicants,
                    scorer=self._score_job_with_llm,
                    match_threshold=self.match_threshold,
                    storage=self.storage,
                    connect_limit=5,
                )
                click.echo(
                    f"  ✅ Completed {len(jobs)} job evaluations for {portal_name}"
                )

                click.secho(f"  ✨ {portal_name} workflow complete", fg="green")
                all_jobs.extend(jobs)

            except Exception as e:
                click.secho(f"  ❌ Error processing {portal_name}: {str(e)}", fg="red")
                logger.error(f"Error scraping {portal_name}: {str(e)}")

        click.echo("\n" + "=" * 80)
        click.secho(
            f"✅ All portals processed! Total jobs scraped: {len(all_jobs)}",
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
        click.echo("=" * 150)

        table_data = []
        for i, job in enumerate(jobs, 1):
            table_data.append(
                [
                    i,
                    job.get("Title", "")[:20],
                    job.get("Company", "")[:15],
                    job.get("Location", "Remote")[:12],
                    job.get("Source", "")[:10],
                    job.get("Posted Date", "N/A")[:10],
                ]
            )

        headers = ["#", "Title", "Company", "Location", "Source", "Posted Date"]
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Show CSV location
        click.secho("\n📁 Jobs stored in: data/jobs.csv", fg="green")
        if Path("data/jobs.xlsx").exists():
            click.secho("📊 Excel file available: data/jobs.xlsx", fg="green")

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
@click.option("--max-applicants", default=100, help="Max applicants threshold")
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
    """Export CSV jobs to Excel."""
    finder = JobFinder()
    click.echo("\n📊 Exporting to Excel...")

    if finder.storage.export_to_excel():
        click.secho("✅ Exported jobs to data/jobs.xlsx", fg="green")
    else:
        click.secho("❌ Export failed. Make sure openpyxl is installed:", fg="red")
        click.echo("pip install openpyxl")


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
