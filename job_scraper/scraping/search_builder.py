"""
LinkedIn search URL builder
Constructs LinkedIn job search URLs with filters
"""

from urllib.parse import quote


class LinkedInSearchBuilder:
    """
    Builds LinkedIn job search URLs with various filters and options.

    Attributes:
        BASE_URL (str): The base URL for LinkedIn job search.
    """

    BASE_URL = "https://www.linkedin.com/jobs/search/"

    def __init__(self):
        pass

    def build_search_url(
        self,
        keywords: str | None = None,
        location: str | None = None,
        remote: bool | None = None,
        experience_levels: list[str] | None = None,
        date_posted: str | None = None,
        easy_apply: bool | None = None,
    ) -> str:
        """
        Build a LinkedIn job search URL with filters for keywords, location, remote, experience level, date posted, and Easy Apply.

        Args:
            keywords (str | None): Job title or keywords (e.g., "Software Engineer").
            location (str | None): Location string (e.g., "United States", "New York, NY").
            remote (bool | None): Whether to filter for remote jobs (True) or not (None for any).
            experience_levels (list[str] | None): List of experience levels (e.g., ["Internship", "Entry level", "Associate"]).
            date_posted (str | None): Time period filter (e.g., "r86400" for past 24h, "r604800" for past week, "r2592000" for past month). Can use custom values like "r3600" for past hour.
            easy_apply (bool | None): Whether to filter for Easy Apply jobs only.

        Returns:
            str: Complete LinkedIn job search URL with encoded parameters.
        """
        params = []

        # Keywords (job title)
        if keywords:
            params.append(f"keywords={quote(keywords)}")

        # Location
        if location:
            params.append(f"location={quote(location)}")

        # Remote filter (f_WT=2 means remote jobs)
        if remote:
            params.append("f_WT=2")

        # Experience levels
        # LinkedIn experience level codes:
        # 1 = Internship
        # 2 = Entry level
        # 3 = Associate
        # 4 = Mid-Senior level
        # 5 = Director
        # 6 = Executive
        if experience_levels:
            exp_codes = []
            exp_map = {
                "Internship": "1",
                "Entry level": "2",
                "Associate": "3",
                "Mid-Senior level": "4",
                "Director": "5",
                "Executive": "6",
            }
            for level in experience_levels:
                if level in exp_map:
                    exp_codes.append(exp_map[level])

            if exp_codes:
                params.append(f"f_E={','.join(exp_codes)}")

        # Date posted filter (f_TPR=r86400 for past 24h)
        # Common values:
        # r86400 = Past 24 hours
        # r604800 = Past week
        # r2592000 = Past month
        # Custom: r3600 = Past hour
        if date_posted:
            # Clamp to LinkedIn-allowed recency window (1h to 24h) and normalize format r<number>
            import re

            match = re.match(r"r(\d+)", str(date_posted).strip())
            if match:
                seconds = int(match.group(1))
                clamped = max(3600, min(seconds, 86400))
                params.append(f"f_TPR=r{clamped}")
            else:
                params.append("f_TPR=r86400")

        # Easy Apply filter
        if easy_apply:
            params.append("f_AL=true")

        # Position (start from 0)
        params.append("position=1")
        params.append("pageNum=0")

        # Combine all parameters
        url = self.BASE_URL
        if params:
            url += "?" + "&".join(params)

        return url

    def build_role_search_url(
        self,
        role: dict,
        search_settings: dict,
    ) -> str:
        """
        Build a LinkedIn job search URL from a role configuration and search settings.

        Args:
            role (dict): Role configuration dictionary from roles.json. Expected keys: title, location, experience_levels, remote, keywords.
            search_settings (dict): Search settings dictionary from roles.json. Expected keys: date_posted, applicant_limit, requires_sponsorship.

        Returns:
            str: Complete LinkedIn job search URL.
        """
        # Extract role fields
        title = role.get("title", "")
        location = role.get("location", "")
        experience_levels = role.get("experience_levels", [])
        remote = role.get("remote", False)

        # Extract search settings
        date_posted = search_settings.get("date_posted", "r86400")

        return self.build_search_url(
            keywords=title,
            location=location,
            remote=remote,
            experience_levels=experience_levels,
            date_posted=date_posted,
        )

    def get_next_page_url(self, current_url: str, page_num: int) -> str:
        """
        Get the URL for the next page of search results by updating the pageNum parameter.

        Args:
            current_url (str): Current search URL.
            page_num (int): Page number to fetch (0-indexed).

        Returns:
            str: URL with updated page number.
        """
        # Replace or add pageNum parameter
        if "pageNum=" in current_url:
            # Replace existing pageNum
            import re

            new_url = re.sub(r"pageNum=\d+", f"pageNum={page_num}", current_url)
        else:
            # Add pageNum parameter
            separator = "&" if "?" in current_url else "?"
            new_url = f"{current_url}{separator}pageNum={page_num}"

        return new_url
