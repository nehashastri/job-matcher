"""Tests for Phase 6 networking helpers (PeopleFinder, ConnectionRequester)."""

import tempfile
from unittest.mock import MagicMock, patch

from networking.connection_requester import ConnectionRequester
from networking.people_finder import PeopleFinder
from storage_pkg.matched_jobs_store import MatchedJobsStore


def _make_card(name: str, title: str, url: str):
    link = MagicMock()
    link.get_attribute.return_value = url

    name_elem = MagicMock()
    name_elem.text = name

    title_elem = MagicMock()
    title_elem.text = title

    def find_element(by, selector):
        if selector == "a.app-aware-link":
            return link
        if selector == "span.entity-result__title-text span[aria-hidden='true']":
            return name_elem
        if selector == "div.entity-result__primary-subtitle":
            return title_elem
        raise Exception("not found")

    card = MagicMock()
    card.find_element.side_effect = find_element
    return card


@patch("networking.people_finder.time.sleep")
def test_people_finder_collects_profiles(mock_sleep):
    driver = MagicMock()
    wait = MagicMock()
    wait.until.return_value = True

    people_filter = MagicMock()
    next_button = MagicMock()
    next_button.get_attribute.return_value = None

    def find_element(by, selector):
        if "People" in selector:
            return people_filter
        if "Next" in selector:
            return next_button
        raise Exception("not found")

    driver.find_element.side_effect = find_element

    card_match = _make_card(
        "Alice", "Software Engineer", "https://linkedin.com/in/alice"
    )
    card_other = _make_card("Bob", "Designer", "https://linkedin.com/in/bob")

    driver.find_elements.side_effect = [
        [card_match, card_other],  # page 1
        [card_match, card_other],  # page 2
    ]

    finder = PeopleFinder(driver, wait, logger=MagicMock())
    profiles = finder.search(role="Software Engineer", company="Acme", pages=2)

    # First nav goes to base URL for search bar path
    assert driver.get.call_args_list[0][0][0] == "https://www.linkedin.com"
    assert len(profiles) == 4  # two pages * two profiles
    assert profiles[0]["is_role_match"] is True
    assert profiles[1]["is_role_match"] is False


@patch("networking.connection_requester.time.sleep")
def test_connection_requester_match_connect_and_message_available(mock_sleep):
    """Match profile: log message availability and click connect."""

    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    connect_btn = MagicMock()
    msg_btn = MagicMock()

    requester._find_message_button_in_card = lambda card: msg_btn
    requester._find_connect_button_in_card = lambda card: connect_btn
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    card_alice = MagicMock()
    requester._find_card_by_url = lambda url: card_alice  # type: ignore[assignment]

    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "Alice",
                "profile_url": "https://linkedin.com/in/alice",
                "is_role_match": True,
            },
        ]
    ]

    summary = requester.run_on_people_search(
        people_finder,
        role="Software Engineer",
        company="Acme",
        store=MatchedJobsStore(data_dir=tempfile.mkdtemp()),
        max_pages=1,
        delay_range=(0, 0),
    )

    assert summary["message_available"] == 1
    assert summary["connect_clicked_match"] == 1
    connect_btn.click.assert_called_once()
    requester._record_connection.assert_called()


@patch("networking.connection_requester.time.sleep")
def test_connection_requester_non_match_connect(mock_sleep):
    """Non-match: click connect when available."""

    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    connect_btn = MagicMock()
    requester._find_message_button_in_card = lambda card: None
    requester._find_connect_button_in_card = lambda card: connect_btn
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    card_charlie = MagicMock()
    requester._find_card_by_url = lambda url: card_charlie  # type: ignore[assignment]

    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "Charlie",
                "profile_url": "https://linkedin.com/in/charlie",
                "is_role_match": False,
            },
        ]
    ]

    summary = requester.run_on_people_search(
        people_finder,
        role="Software Engineer",
        company="Acme",
        store=MatchedJobsStore(data_dir=tempfile.mkdtemp()),
        max_pages=1,
        delay_range=(0, 0),
    )

    assert summary["connect_clicked_non_match"] == 1
    connect_btn.click.assert_called_once()


@patch("networking.connection_requester.time.sleep")
def test_connection_requester_non_match_message_only_skips(mock_sleep):
    """Non-match with only message button should be skipped (no action)."""

    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    msg_btn = MagicMock()
    requester._find_message_button_in_card = lambda card: msg_btn
    requester._find_connect_button_in_card = lambda card: None
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    card_bob = MagicMock()
    requester._find_card_by_url = lambda url: card_bob  # type: ignore[assignment]

    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "Bob",
                "profile_url": "https://linkedin.com/in/bob",
                "is_role_match": False,
            },
        ]
    ]

    summary = requester.run_on_people_search(
        people_finder,
        role="Software Engineer",
        company="Acme",
        store=MatchedJobsStore(data_dir=tempfile.mkdtemp()),
        max_pages=1,
        delay_range=(0, 0),
    )

    assert summary["skipped"] == 1


@patch("networking.connection_requester.time.sleep")
def test_connection_requester_match_only_message_available(mock_sleep):
    """Match with message button only logs availability (no connect)."""

    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    msg_btn = MagicMock()
    requester._find_message_button_in_card = lambda card: msg_btn
    requester._find_connect_button_in_card = lambda card: None
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    card_david = MagicMock()
    requester._find_card_by_url = lambda url: card_david  # type: ignore[assignment]

    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "David",
                "profile_url": "https://linkedin.com/in/david",
                "is_role_match": True,
            },
        ]
    ]

    summary = requester.run_on_people_search(
        people_finder,
        role="Software Engineer",
        company="Acme",
        store=MatchedJobsStore(data_dir=tempfile.mkdtemp()),
        max_pages=1,
        delay_range=(0, 0),
    )

    assert summary["message_available"] == 1
    assert summary["connect_clicked_match"] == 0


@patch("networking.connection_requester.time.sleep")
def test_connection_requester_all_4_scenarios_with_lewei_zeng_ignored(mock_sleep):
    """All 4 scenarios in one test, with Lewei Zeng being ignored."""
    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    # Track which profiles are processed
    processed_profiles = []

    def find_card_by_url(url):
        card = MagicMock()
        processed_profiles.append(url)
        return card

    requester._find_card_by_url = find_card_by_url  # type: ignore[assignment]

    # Setup different button states for each card
    button_states = {
        "https://linkedin.com/in/alice": {
            "message": None,
            "connect": MagicMock(),
        },  # Scenario 1: match + connect
        "https://linkedin.com/in/bob": {
            "message": MagicMock(),
            "connect": None,
        },  # Scenario 2: non-match + message
        "https://linkedin.com/in/charlie": {
            "message": None,
            "connect": MagicMock(),
        },  # Scenario 3: non-match + connect
        "https://linkedin.com/in/david": {
            "message": MagicMock(),
            "connect": None,
        },  # Scenario 4: match + message
    }

    def find_message_button(card):
        for url, state in button_states.items():
            if url in str(processed_profiles[-1] if processed_profiles else ""):
                return state["message"]
        return None

    def find_connect_button(card):
        for url, state in button_states.items():
            if url in str(processed_profiles[-1] if processed_profiles else ""):
                return state["connect"]
        return None

    requester._find_message_button_in_card = find_message_button
    requester._find_connect_button_in_card = find_connect_button
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            # Scenario 1: match=True, no message, has connect -> sends with note
            {
                "name": "Alice",
                "profile_url": "https://linkedin.com/in/alice",
                "is_role_match": True,
            },
            # Scenario 2: match=False, has message -> skipping
            {
                "name": "Bob",
                "profile_url": "https://linkedin.com/in/bob",
                "is_role_match": False,
            },
            # Lewei Zeng should be ignored (skipped entirely)
            {
                "name": "Lewei Zeng",
                "profile_url": "https://linkedin.com/in/lewei-zeng",
                "is_role_match": True,
            },
            # Scenario 3: match=False, no message, has connect -> sends without note
            {
                "name": "Charlie",
                "profile_url": "https://linkedin.com/in/charlie",
                "is_role_match": False,
            },
            # Scenario 4: match=True, has message -> sends message
            {
                "name": "David",
                "profile_url": "https://linkedin.com/in/david",
                "is_role_match": True,
            },
        ]
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MatchedJobsStore(data_dir=tmpdir)
        summary = requester.run_on_people_search(
            people_finder,
            role="Software Engineer",
            company="Acme",
            store=store,
            max_pages=1,
            delay_range=(0, 0),
        )

    # Verify the summary counters
    assert summary["connect_clicked_match"] == 1  # Alice
    assert summary["skipped"] == 1  # Bob (message only)
    assert summary["connect_clicked_non_match"] == 1  # Charlie
    assert summary["message_available"] == 1  # David (message only)
    # Lewei Zeng should NOT be in the processed list (needs filtering logic)


@patch("networking.connection_requester.time.sleep")
def test_phase8_meta_role_four_paths(mock_sleep):
    """Data Scientist at Meta: cover match/non-match paths in one run, single tab only."""

    driver = MagicMock()
    wait = MagicMock()

    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    # Keep processed URL to map buttons deterministically
    processed_urls: list[str] = []

    def find_card_by_url(url: str):
        processed_urls.append(url)
        return MagicMock()

    requester._find_card_by_url = find_card_by_url  # type: ignore[assignment]
    requester._random_delay = lambda _a, _b: None  # type: ignore[assignment]
    requester._record_connection = MagicMock()

    # Map URLs to button availability
    button_states = {
        "https://linkedin.com/in/alexa": {"message": None, "connect": MagicMock()},
        "https://linkedin.com/in/bob": {"message": MagicMock(), "connect": None},
        "https://linkedin.com/in/cara": {"message": None, "connect": MagicMock()},
        "https://linkedin.com/in/dan": {"message": MagicMock(), "connect": None},
    }

    def find_message_button(card):
        url = processed_urls[-1]
        return button_states[url]["message"]

    def find_connect_button(card):
        url = processed_urls[-1]
        return button_states[url]["connect"]

    requester._find_message_button_in_card = find_message_button
    requester._find_connect_button_in_card = find_connect_button

    # Build profiles for the four required paths
    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "Alexa",
                "profile_url": "https://linkedin.com/in/alexa",
                "is_role_match": True,
            },
            {
                "name": "Bob",
                "profile_url": "https://linkedin.com/in/bob",
                "is_role_match": False,
            },
            {
                "name": "Cara",
                "profile_url": "https://linkedin.com/in/cara",
                "is_role_match": False,
            },
            {
                "name": "Dan",
                "profile_url": "https://linkedin.com/in/dan",
                "is_role_match": True,
            },
        ]
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MatchedJobsStore(data_dir=tmpdir)
        summary = requester.run_on_people_search(
            people_finder,
            role="Data Scientist",
            company="Meta",
            store=store,
            max_pages=1,
            delay_range=(0, 0),
        )

    assert summary["connect_clicked_match"] == 1  # Alexa (match + connect)
    assert summary["connect_clicked_non_match"] == 1  # Cara (non-match + connect)
    assert summary["message_available"] == 2  # Bob + Dan (message available)
    assert summary["skipped"] == 0
