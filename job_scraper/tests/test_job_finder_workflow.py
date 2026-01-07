
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Ensure 'app' is importable when running from job_scraper root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.job_finder import JobFinder

class TestJobFinderWorkflow(unittest.TestCase):
    @patch('app.job_finder.JobStorage')
    @patch('notifications.email_notifier.EmailNotifier')
    @patch('networking.people_finder.PeopleFinder')
    def test_process_jobs_scrapes_and_notifies(self, MockPeopleFinder, MockEmailNotifier, MockJobStorage):
        # Setup mocks
        mock_storage = MockJobStorage.return_value
        mock_people_finder = MockPeopleFinder.return_value
        mock_email_notifier = MockEmailNotifier.return_value

        # Simulate add_job returns True (job is new and added)
        mock_storage.add_job.return_value = True
        # Simulate people scraping returns profiles
        mock_people_finder.scrape_people_cards.return_value = [{'name': 'Alice'}, {'name': 'Bob'}]
        # Simulate add_people_profiles
        mock_storage.add_people_profiles.return_value = None
        # Simulate email notification
        mock_email_notifier.send_job_notification.return_value = None

        # Create JobFinder instance
        finder = JobFinder()
        finder.storage = mock_storage
        finder.match_threshold = 5.0  # Lower threshold for test
        finder._score_job_with_llm = MagicMock(return_value=8.5)

        # Prepare test job and scraper with driver/wait
        job = {'title': 'Engineer', 'company': 'TestCo', 'url': 'http://test', 'applicant_count': 10}
        jobs = [job]
        mock_scraper = MagicMock()
        mock_scraper.driver = MagicMock()
        mock_scraper.wait = MagicMock()

        # Run _process_jobs
        matched = finder._process_jobs('LinkedIn', jobs, mock_scraper)

        # Assert job was matched and processed
        self.assertEqual(matched, [job])
        mock_storage.add_job.assert_called_once()
        mock_people_finder.scrape_people_cards.assert_called_once_with('Engineer', 'TestCo')
        mock_storage.add_people_profiles.assert_called_once_with(
            [{'name': 'Alice'}, {'name': 'Bob'}], searched_job_title='Engineer')
        mock_email_notifier.send_job_notification.assert_called_once_with(job, match_profiles=[{'name': 'Alice'}, {'name': 'Bob'}])

if __name__ == '__main__':
    unittest.main()
