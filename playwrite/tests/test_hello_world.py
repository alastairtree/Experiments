"""Playwright tests for the Hello World web server."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"


def screenshot(page: Page, name: str) -> None:
    """Save a full-page screenshot to the screenshots/ directory."""
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)


class TestIndexPage:
    """Tests for the Hello World index page."""

    def test_page_title(self, page: Page, live_server: str) -> None:
        """Index page should have 'Hello World' in the title."""
        page.goto(live_server)
        expect(page).to_have_title("Hello World")
        screenshot(page, "01_index_page")

    def test_heading_present(self, page: Page, live_server: str) -> None:
        """Index page should display an H1 with 'Hello World!'."""
        page.goto(live_server)
        expect(page.locator("h1")).to_have_text("Hello World!")
        screenshot(page, "02_heading")

    def test_form_elements_present(self, page: Page, live_server: str) -> None:
        """Index page should have a name input and a submit button."""
        page.goto(live_server)
        expect(page.locator("#name")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()
        screenshot(page, "03_form_elements")


class TestNameSubmission:
    """Tests for name submission and greeting display."""

    def test_submit_name_redirects_to_greet(self, page: Page, live_server: str) -> None:
        """Submitting a name should navigate to /greet."""
        page.goto(live_server)
        page.fill("#name", "Alice")
        screenshot(page, "04_name_entered")
        page.click("button[type='submit']")
        page.wait_for_url("**/greet")
        screenshot(page, "05_greet_page")

    def test_greet_page_shows_name(self, page: Page, live_server: str) -> None:
        """The greeting page should display the submitted name."""
        page.goto(live_server)
        page.fill("#name", "Bob")
        page.click("button[type='submit']")
        page.wait_for_url("**/greet")
        expect(page.locator("h1")).to_have_text("Hello, Bob!")
        screenshot(page, "06_greet_bob")

    def test_greet_page_title_includes_name(self, page: Page, live_server: str) -> None:
        """The greeting page title should include the submitted name."""
        page.goto(live_server)
        page.fill("#name", "Charlie")
        page.click("button[type='submit']")
        page.wait_for_url("**/greet")
        expect(page).to_have_title("Hello Charlie!")
        screenshot(page, "07_greet_charlie_title")

    def test_go_back_link(self, page: Page, live_server: str) -> None:
        """The greet page should have a 'Go back' link to the index."""
        page.goto(live_server)
        page.fill("#name", "Dave")
        page.click("button[type='submit']")
        page.wait_for_url("**/greet")
        back_link = page.locator("a", has_text="Go back")
        expect(back_link).to_be_visible()
        screenshot(page, "08_go_back_link")
        back_link.click()
        expect(page).to_have_url(live_server + "/")
        screenshot(page, "09_back_on_index")

    def test_empty_name_defaults_to_world(self, page: Page, live_server: str) -> None:
        """Submitting with an empty name should display 'Hello, World!'."""
        page.goto(live_server)
        page.fill("#name", "")
        page.click("button[type='submit']")
        page.wait_for_url("**/greet")
        expect(page.locator("h1")).to_have_text("Hello, World!")
        screenshot(page, "10_greet_empty_name")
