"""
Tests for Phase 2: LinkedIn Job Scraping
Tests search URL builder, job list scraper, and job detail scraper
"""

from unittest.mock import MagicMock, patch

import pytest
from scraping.job_detail_scraper import JobDetailScraper
from scraping.job_list_scraper import JobListScraper
from scraping.linkedin_scraper import LinkedInScraper
from scraping.search_builder import LinkedInSearchBuilder


class TestSearchBuilder:
    """Tests for LinkedIn search URL builder"""

    def setup_method(self):
        """Set up test fixtures"""
        self.builder = LinkedInSearchBuilder()

    def test_build_basic_search_url(self):
        """Test building a basic search URL with keywords and location"""
        url = self.builder.build_search_url(
            keywords="Software Engineer", location="United States"
        )

        assert "https://www.linkedin.com/jobs/search/" in url
        assert "keywords=Software%20Engineer" in url
        assert "location=United%20States" in url

    def test_build_url_with_remote_filter(self):
        """Test building URL with remote filter"""
        url = self.builder.build_search_url(keywords="Software Engineer", remote=True)

        assert "f_WT=2" in url

    def test_build_url_with_experience_levels(self):
        """Test building URL with experience level filters"""
        url = self.builder.build_search_url(
            keywords="Software Engineer",
            experience_levels=["Internship", "Entry level", "Associate"],
        )

        assert "f_E=1,2,3" in url

    def test_build_url_with_date_posted_24h(self):
        """Test building URL with date_posted filter for past 24 hours"""
        url = self.builder.build_search_url(
            keywords="Software Engineer", date_posted="r86400"
        )

        assert "f_TPR=r86400" in url

    def test_build_url_with_custom_date_posted(self):
        """Test building URL with custom date_posted value (e.g., r3600 for past hour)"""
        url = self.builder.build_search_url(
            keywords="Software Engineer", date_posted="r3600"
        )

        assert "f_TPR=r3600" in url

    def test_build_url_with_all_filters(self):
        """Test building URL with all possible filters"""
        url = self.builder.build_search_url(
            keywords="Machine Learning Engineer",
            location="New York, NY",
            remote=True,
            experience_levels=["Entry level", "Associate"],
            date_posted="r604800",
            easy_apply=True,
        )

        assert "keywords=Machine%20Learning%20Engineer" in url
        assert "location=New%20York%2C%20NY" in url
        assert "f_WT=2" in url
        assert "f_E=2,3" in url
        assert "f_TPR=r604800" in url
        assert "f_AL=true" in url

    def test_build_role_search_url(self):
        """Test building URL from role configuration"""
        role = {
            "title": "Data Engineer",
            "location": "United States",
            "experience_levels": ["Entry level", "Associate"],
            "remote": True,
        }
        search_settings = {"date_posted": "r86400", "applicant_limit": 100}

        url = self.builder.build_role_search_url(role, search_settings)

        assert "keywords=Data%20Engineer" in url
        assert "location=United%20States" in url
        assert "f_WT=2" in url
        assert "f_E=2,3" in url
        assert "f_TPR=r86400" in url

    def test_get_next_page_url_adds_page_num(self):
        """Test getting next page URL adds pageNum parameter"""
        current_url = "https://www.linkedin.com/jobs/search/?keywords=Engineer"
        next_url = self.builder.get_next_page_url(current_url, 1)

        assert "pageNum=1" in next_url

    def test_get_next_page_url_replaces_existing(self):
        """Test getting next page URL replaces existing pageNum"""
        current_url = (
            "https://www.linkedin.com/jobs/search/?keywords=Engineer&pageNum=0"
        )
        next_url = self.builder.get_next_page_url(current_url, 2)

        assert "pageNum=2" in next_url
        assert "pageNum=0" not in next_url


class TestJobListScraper:
    """Tests for LinkedIn job list scraper"""

    def setup_method(self):
        """Set up test fixtures"""
        self.driver = MagicMock()
        self.config = MagicMock()
        self.config.max_jobs_per_role = 50
        self.config.skip_viewed_jobs = True
        self.config.request_delay_min = 2.0
        self.config.request_delay_max = 5.0

        self.scraper = JobListScraper(self.driver, self.config)

    @patch("scraping.job_list_scraper.time.sleep")
    def test_extract_job_from_card_success(self, mock_sleep):
        """Test extracting job information from a job card"""
        # Mock job card element
        card = MagicMock()

        # Mock job link
        job_link = MagicMock()
        job_link.get_attribute.return_value = (
            "https://www.linkedin.com/jobs/view/1234567890/?refId=abc"
        )
        job_link.text = "Software Engineer"
        card.find_element.side_effect = [
            job_link,  # First call for job link
            MagicMock(text="Acme Corp"),  # Company name
            MagicMock(text="New York, NY"),  # Location
        ]

        # Mock card attributes
        card.get_attribute.return_value = ""
        card.value_of_css_property.return_value = "1.0"

        job = self.scraper._extract_job_from_card(card)

        assert job is not None
        assert job["job_id"] == "1234567890"
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Acme Corp"
        assert job["location"] == "New York, NY"
        assert not job["is_viewed"]
        assert "1234567890" in job["job_url"]

    @patch("scraping.job_list_scraper.time.sleep")
    def test_extract_job_identifies_viewed_job(self, mock_sleep):
        """Test that viewed jobs are correctly identified"""
        card = MagicMock()

        job_link = MagicMock()
        job_link.get_attribute.return_value = (
            "https://www.linkedin.com/jobs/view/1234567890/"
        )
        job_link.text = "Software Engineer"
        card.find_element.side_effect = [
            job_link,
            MagicMock(text="Acme Corp"),
            MagicMock(text="New York, NY"),
        ]

        # Mark as viewed (reduced opacity or special class)
        card.get_attribute.return_value = "job-card is-dismissed"
        card.value_of_css_property.return_value = "0.6"

        job = self.scraper._extract_job_from_card(card)

        assert job is not None
        assert job["is_viewed"]

    @patch("scraping.job_list_scraper.time.sleep")
    def test_scrape_job_list_filters_viewed_jobs(self, mock_sleep):
        """Test that viewed jobs are filtered out when skip_viewed_jobs is True"""
        self.config.skip_viewed_jobs = True

        # Mock driver navigation and elements
        self.driver.get = MagicMock()

        # Mock job cards - 3 jobs, 1 viewed
        card1 = self._create_mock_job_card("111", "Job 1", "Company A", False)
        card2 = self._create_mock_job_card("222", "Job 2", "Company B", True)  # Viewed
        card3 = self._create_mock_job_card("333", "Job 3", "Company C", False)

        self.driver.find_elements.return_value = [card1, card2, card3]
        self.driver.find_element.return_value = MagicMock()

        # Mock wait
        with patch.object(self.scraper, "wait") as mock_wait:
            mock_wait.until.return_value = True

            with patch.object(self.scraper, "_scroll_to_load_more", return_value=False):
                jobs = self.scraper.scrape_job_list("https://test.com", max_jobs=10)

        # Should only return unviewed jobs
        assert len(jobs) == 2
        assert all(not job["is_viewed"] for job in jobs)

    def _create_mock_job_card(self, job_id, title, company, is_viewed):
        """Helper to create a mock job card"""
        card = MagicMock()

        job_link = MagicMock()
        job_link.get_attribute.return_value = (
            f"https://www.linkedin.com/jobs/view/{job_id}/"
        )
        job_link.text = title

        card.find_element.side_effect = [
            job_link,
            MagicMock(text=company),
            MagicMock(text="Location"),
        ]

        if is_viewed:
            card.get_attribute.return_value = "job-card is-dismissed"
            card.value_of_css_property.return_value = "0.6"
        else:
            card.get_attribute.return_value = "job-card"
            card.value_of_css_property.return_value = "1.0"

        return card

    @patch("scraping.job_list_scraper.time.sleep")
    def test_scrape_handles_stale_element(self, mock_sleep):
        """Test that stale element exceptions are handled gracefully"""
        from selenium.common.exceptions import StaleElementReferenceException

        card = MagicMock()
        card.find_element.side_effect = StaleElementReferenceException("Stale element")

        job = self.scraper._extract_job_from_card(card)

        # Should return None and not crash
        assert job is None


class TestJobDetailScraper:
    """Tests for LinkedIn job detail scraper"""

    def setup_method(self):
        """Set up test fixtures"""
        self.driver = MagicMock()
        self.config = MagicMock()
        self.config.request_delay_min = 2.0
        self.config.request_delay_max = 5.0

        self.scraper = JobDetailScraper(self.driver, self.config)

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_extract_job_details_complete(self, mock_sleep):
        """Test extracting complete job details"""
        job_id = "1234567890"

        # Mock description element
        desc_elem = MagicMock()
        desc_elem.text = "Full job description with requirements and responsibilities"
        desc_elem.find_element.side_effect = Exception("No show more button")

        # Mock criteria elements
        criteria_items = [
            MagicMock(text="Seniority level\nEntry level"),
            MagicMock(text="Employment type\nFull-time"),
            MagicMock(text="Job function\nEngineering"),
        ]

        # Mock other elements
        posted_elem = MagicMock(text="2 days ago")
        applicant_elem = MagicMock(text="50 applicants")
        workplace_elem = MagicMock(text="Remote")

        def mock_find_element(by, selector):
            if "jobs-description__content" in selector:
                return desc_elem
            elif "posted-date" in selector:
                return posted_elem
            elif "applicant-count" in selector:
                return applicant_elem
            elif "workplace-type" in selector:
                return workplace_elem
            raise Exception(f"Unknown selector: {selector}")

        self.driver.find_element.side_effect = mock_find_element
        self.driver.find_elements.return_value = criteria_items

        details = self.scraper._extract_job_details(job_id)

        assert details is not None
        assert details["job_id"] == job_id
        assert (
            details["description"]
            == "Full job description with requirements and responsibilities"
        )
        assert "Entry level" in details["seniority"]
        assert "Full-time" in details["employment_type"]
        assert "Engineering" in details["job_function"]
        assert details["posted_time"] == "2 days ago"
        assert details["applicant_count"] == 50
        assert details["remote_eligible"]

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_extract_job_details_handles_missing_elements(self, mock_sleep):
        """Test that missing elements are handled gracefully"""
        from selenium.common.exceptions import NoSuchElementException

        job_id = "1234567890"

        # Mock minimal elements - description only
        desc_elem = MagicMock(text="Job description")
        desc_elem.find_element.side_effect = NoSuchElementException()

        def mock_find_element(by, selector):
            if "jobs-description__content" in selector:
                return desc_elem
            raise NoSuchElementException()

        self.driver.find_element.side_effect = mock_find_element
        self.driver.find_elements.return_value = []

        details = self.scraper._extract_job_details(job_id)

        assert details is not None
        assert details["job_id"] == job_id
        assert details["description"] == "Job description"
        assert details["seniority"] == "Unknown"
        assert details["posted_time"] == "Unknown"
        assert details["applicant_count"] is None

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_scrape_job_details_with_retries(self, mock_sleep):
        """Test that job detail scraping retries on failure"""
        from selenium.common.exceptions import TimeoutException

        job_id = "1234567890"

        # Mock clicking job card
        with patch.object(self.scraper, "_click_job_card"):
            # Mock wait to fail first time, succeed second time
            attempt_count = [0]

            def mock_until(condition):
                attempt_count[0] += 1
                if attempt_count[0] == 1:
                    raise TimeoutException()
                return True

            self.scraper.wait.until = mock_until

            # Mock successful extraction on retry
            with patch.object(self.scraper, "_extract_job_details") as mock_extract:
                mock_extract.return_value = {"job_id": job_id, "title": "Test Job"}

                result = self.scraper.scrape_job_details(job_id, max_retries=3)

        assert result is not None
        assert result["job_id"] == job_id

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_scrape_handles_stale_element_with_retry(self, mock_sleep):
        """Test that stale element exceptions trigger retry"""
        from selenium.common.exceptions import StaleElementReferenceException

        job_id = "1234567890"

        with patch.object(self.scraper, "_click_job_card") as mock_click:
            # Fail with stale element first time
            mock_click.side_effect = [
                StaleElementReferenceException(),
                None,  # Success on retry
            ]

            with patch.object(self.scraper, "wait") as mock_wait:
                mock_wait.until.return_value = True

                with patch.object(self.scraper, "_extract_job_details") as mock_extract:
                    mock_extract.return_value = {"job_id": job_id}

                    result = self.scraper.scrape_job_details(job_id, max_retries=3)

        # Should succeed on retry
        assert result is not None
        assert mock_click.call_count == 2


class TestPaginationMath:
    """Pagination calculations should match LinkedIn page sizing."""

    def test_compute_total_pages_caps_results(self):
        assert LinkedInScraper._compute_total_pages(0) == 0
        assert LinkedInScraper._compute_total_pages(1) == 1
        assert LinkedInScraper._compute_total_pages(25) == 1
        assert LinkedInScraper._compute_total_pages(26) == 2
        assert LinkedInScraper._compute_total_pages(240, cap=3) == 3
        assert LinkedInScraper._compute_total_pages(241, cap=3) == 3

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_detect_remote_from_description(self, mock_sleep):
        """Test that remote eligibility is detected from job description"""
        job_id = "1234567890"

        # Mock description with remote keywords
        desc_elem = MagicMock()
        desc_elem.text = "This is a remote position. Work from home anywhere in the US."
        desc_elem.find_element.side_effect = Exception()

        self.driver.find_element.return_value = desc_elem
        self.driver.find_elements.return_value = []

        details = self.scraper._extract_job_details(job_id)

        assert details is not None
        assert details["remote_eligible"]

    @patch("scraping.job_detail_scraper.time.sleep")
    def test_pagination_with_multiple_pages(self, mock_sleep):
        """Test scraping multiple pages of job results"""
        # This is more of an integration test concept
        # Testing that the scraper can handle pagination
        builder = LinkedInSearchBuilder()

        base_url = "https://www.linkedin.com/jobs/search/?keywords=Engineer"

        page_1_url = builder.get_next_page_url(base_url, 1)
        page_2_url = builder.get_next_page_url(base_url, 2)

        assert "pageNum=1" in page_1_url
        assert "pageNum=2" in page_2_url
        assert page_1_url != page_2_url


# Fixtures for integration testing (would need real browser)
@pytest.fixture
def mock_linkedin_session():
    """Mock LinkedIn session for testing"""
    driver = MagicMock()
    driver.get = MagicMock()
    driver.find_element = MagicMock()
    driver.find_elements = MagicMock(return_value=[])
    return driver


@pytest.fixture
def test_config():
    """Test configuration"""
    config = MagicMock()
    config.max_jobs_per_role = 50
    config.skip_viewed_jobs = True
    config.request_delay_min = 0.1  # Faster for tests
    config.request_delay_max = 0.2
    config.max_retries = 3
    return config


# Integration test examples (commented out - would require real browser)
"""
def test_full_scraping_workflow(mock_linkedin_session, test_config):
    # This would test the full workflow:
    # 1. Build search URL
    # 2. Scrape job list
    # 3. Scrape job details for each job
    # 4. Handle errors and retries
    pass

def test_scrape_with_real_linkedin_page():
    # This would require a real browser and LinkedIn access
    # Test against actual LinkedIn HTML structure
    pass
"""
