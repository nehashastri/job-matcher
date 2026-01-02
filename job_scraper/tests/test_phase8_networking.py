"""Tests for Phase 8 networking helpers (PeopleFinder, ConnectionRequester)."""

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
def test_connection_requester_runs_in_page_with_quotas(mock_sleep):
    driver = MagicMock()
    wait = MagicMock()

    connect_btn_match = MagicMock()
    connect_btn_nonmatch = MagicMock()
    send_btn = MagicMock()
    send_btn_plain = MagicMock()
    add_note_btn = MagicMock()
    textarea = MagicMock()

    # _send_invite will be reached twice (match with note, non-match without)
    requester = ConnectionRequester(driver, wait, logger=MagicMock())

    # Stub helpers to stay in-page
    requester._find_message_button_in_card = lambda card: None
    requester._send_invite = MagicMock(return_value=True)
    requester._add_note = MagicMock()
    requester._random_delay = lambda _a, _b: None

    card_match = MagicMock()
    card_nonmatch = MagicMock()
    card_map = {
        "https://linkedin.com/in/alice": card_match,
        "https://linkedin.com/in/bob": card_nonmatch,
    }
    requester._find_card_by_url = lambda url: card_map.get(url)
    requester._find_connect_button_in_card = (
        lambda card: connect_btn_match if card is card_match else connect_btn_nonmatch
    )

    # Simulate people finder yielding a single page
    people_finder = MagicMock()
    people_finder.iterate_pages.return_value = [
        [
            {
                "name": "Alice",
                "profile_url": "https://linkedin.com/in/alice",
                "is_role_match": True,
            },
            {
                "name": "Bob",
                "profile_url": "https://linkedin.com/in/bob",
                "is_role_match": False,
            },
        ]
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MatchedJobsStore(data_dir=tmpdir)
        summary = requester.run_on_people_search(
            people_finder,
            role="Software Engineer",
            company="Acme",
            message_note_target=1,
            no_note_target=1,
            store=store,
        )

        connections = store.get_all_connections()

    assert summary["messaged"] == 0
    assert summary["sent_with_note"] == 1
    assert summary["sent_without_note"] == 1
    assert summary["pages_processed"] == 1

    requester._add_note.assert_called_once()
    assert len(connections) == 2
    assert connections[0]["Message Sent"] == "Yes"
    assert connections[1]["Message Sent"] == "No"
