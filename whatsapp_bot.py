"""
WhatsApp Web Automation Tool
Uses Selenium + Firefox (GeckoDriver) with persistent session management.
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("whatsapp_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("WhatsAppBot")


# ── XPath / CSS selectors (update if WhatsApp Web changes its DOM) ────────────
class Selectors:
    # Landing / QR screen
    QR_CODE            = '//canvas[@aria-label="Scan me!"]'
    LOADING_PROGRESS   = '//progress'

    # Main UI
    SEARCH_BOX         = '//div[@contenteditable="true"][@data-tab="3"]'
    CHAT_LIST_ITEM     = '//span[@title="{contact}"]'

    # Message composer
    MESSAGE_INPUT      = '//div[@contenteditable="true"][@data-tab="10"]'
    SEND_BUTTON        = '//button[@data-testid="compose-btn-send"]'

    # Incoming messages (last message in open chat)
    LAST_MESSAGE_IN    = (
        '(//div[contains(@class,"message-in")]'
        '//span[contains(@class,"selectable-text")])[last()]'
    )
    LAST_MESSAGE_OUT   = (
        '(//div[contains(@class,"message-out")]'
        '//span[contains(@class,"selectable-text")])[last()]'
    )

    # Attachment / file button
    ATTACH_BUTTON      = '//div[@title="Attach"]'
    ATTACH_IMAGE_INPUT = '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]'

    # New-chat / direct message button
    NEW_CHAT_BUTTON    = '//div[@title="New chat"]'
    CONTACT_SEARCH     = '//p[@class="selectable-text copyable-text"]'


# ── Config dataclass ──────────────────────────────────────────────────────────
@dataclass
class BotConfig:
    """All tuneable parameters in one place."""

    # Path to an existing Firefox profile that already has WhatsApp Web logged in.
    # On Linux : ~/.mozilla/firefox/<profile-id>.default
    # On macOS : ~/Library/Application Support/Firefox/Profiles/<profile-id>
    # On Windows: %APPDATA%\Mozilla\Firefox\Profiles\<profile-id>
    firefox_profile_path: str = "/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr"

    # Optional explicit path to geckodriver binary (leave "" to rely on PATH)
    geckodriver_path: str = ""

    # Run browser in background (no visible window)
    headless: bool = False

    # How long (seconds) to wait for elements before raising TimeoutException
    element_timeout: int = 30

    # How long (seconds) to wait for WhatsApp to finish loading after launch
    load_timeout: int = 60

    # Delay (seconds) between consecutive messages to avoid rate-limits
    send_delay: float = 1.5

    # Extra Firefox preferences
    extra_prefs: dict = field(default_factory=dict)


# ── Core Bot class ────────────────────────────────────────────────────────────
class WhatsAppBot:
    """
    Selenium-powered WhatsApp Web client.

    Usage
    -----
    config = BotConfig(firefox_profile_path="/path/to/profile")
    bot = WhatsAppBot(config)
    bot.start()                              # opens browser + waits for WA load
    bot.open_chat("John Doe")
    bot.send_message("Hello from the bot!")
    bot.quit()
    """

    WHATSAPP_URL = "https://web.whatsapp.com"

    def __init__(self, config: BotConfig):
        self.config = config
        self.driver: Optional[webdriver.Firefox] = None
        self._wait: Optional[WebDriverWait] = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch Firefox with the saved profile and load WhatsApp Web."""
        logger.info("Starting WhatsApp Web session …")
        self.driver = self._build_driver()
        self._wait = WebDriverWait(self.driver, self.config.element_timeout)
        self.driver.get(self.WHATSAPP_URL)
        self._wait_for_load()
        logger.info("WhatsApp Web is ready.")

    def quit(self) -> None:
        """Gracefully close the browser."""
        if self.driver:
            logger.info("Closing browser.")
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.quit()

    # ── Session setup ────────────────────────────────────────────────────────

    def _build_driver(self) -> webdriver.Firefox:
        """Configure and return a Firefox WebDriver instance."""
        options = Options()

        # ── Persistent profile (keeps you logged in) ──────────────────────
        profile_path = self.config.firefox_profile_path
        if profile_path:
            if not Path(profile_path).exists():
                raise FileNotFoundError(
                    f"Firefox profile not found: {profile_path}\n"
                    "Tip: run `firefox -ProfileManager` to see your profiles."
                )
            options.profile = profile_path
            logger.info("Using Firefox profile: %s", profile_path)
        else:
            logger.warning(
                "No firefox_profile_path set – a fresh (temporary) profile "
                "will be used. You will need to scan the QR code."
            )

        # ── Headless mode ─────────────────────────────────────────────────
        if self.config.headless:
            options.add_argument("--headless")
            logger.info("Running in headless mode.")

        # ── Recommended preferences ───────────────────────────────────────
        default_prefs = {
            "dom.webnotifications.enabled": False,   # block notification prompts
            "media.volume_scale": "0.0",             # mute audio
        }
        for key, val in {**default_prefs, **self.config.extra_prefs}.items():
            options.set_preference(key, val)

        # ── GeckoDriver service ───────────────────────────────────────────
        service_kwargs = {}
        if self.config.geckodriver_path:
            service_kwargs["executable_path"] = self.config.geckodriver_path
        service = Service(**service_kwargs)

        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(self.config.load_timeout)
        logger.info("Firefox launched successfully.")
        return driver

    def _wait_for_load(self) -> None:
        """
        Wait until WhatsApp Web finishes loading.
        Detects either the search box (already logged in) or the QR code
        (needs authentication).
        """
        logger.info("Waiting for WhatsApp Web to load (timeout=%ds) …",
                    self.config.load_timeout)
        try:
            # Either the chat search box OR the QR canvas must appear
            WebDriverWait(self.driver, self.config.load_timeout).until(
                lambda d: (
                    self._element_exists(Selectors.SEARCH_BOX)
                    or self._element_exists(Selectors.QR_CODE)
                )
            )
        except TimeoutException:
            raise TimeoutException(
                "WhatsApp Web did not load within "
                f"{self.config.load_timeout} seconds."
            )

        if self._element_exists(Selectors.QR_CODE):
            logger.warning(
                "QR code detected – please scan it with your phone. "
                "The bot will wait up to %d seconds.",
                self.config.load_timeout,
            )
            # Wait for user to scan and the search box to appear
            WebDriverWait(self.driver, self.config.load_timeout).until(
                EC.presence_of_element_located((By.XPATH, Selectors.SEARCH_BOX))
            )
            logger.info("QR code scanned. Session active.")

    # ── Navigation ───────────────────────────────────────────────────────────

    def open_chat(self, contact_name: str) -> None:
        """
        Open the chat for *contact_name* via the search bar.
        Raises TimeoutException if the contact is not found.
        """
        logger.info("Opening chat with: %s", contact_name)
        search = self._find(Selectors.SEARCH_BOX)
        search.click()
        search.clear()
        search.send_keys(contact_name)
        time.sleep(1.0)  # let results populate

        contact_xpath = Selectors.CHAT_LIST_ITEM.format(contact=contact_name)
        try:
            contact = self._wait.until(
                EC.element_to_be_clickable((By.XPATH, contact_xpath))
            )
            contact.click()
            time.sleep(0.8)
            logger.info("Chat opened: %s", contact_name)
        except TimeoutException:
            raise TimeoutException(
                f"Contact '{contact_name}' not found in search results."
            )

    # ── Messaging ────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> None:
        """Type and send a plain-text message in the currently open chat."""
        if not text.strip():
            logger.warning("send_message called with empty text – skipped.")
            return

        logger.info("Sending message: %.60s%s", text, "…" if len(text) > 60 else "")
        msg_box = self._find(Selectors.MESSAGE_INPUT)
        msg_box.click()

        # Handle multi-line messages: newlines → Shift+Enter
        lines = text.split("\n")
        for i, line in enumerate(lines):
            msg_box.send_keys(line)
            if i < len(lines) - 1:
                msg_box.send_keys(Keys.SHIFT + Keys.RETURN)

        msg_box.send_keys(Keys.RETURN)
        time.sleep(self.config.send_delay)

    def send_messages_bulk(self, contact_name: str, messages: List[str]) -> None:
        """Open *contact_name* and send every message in *messages*."""
        self.open_chat(contact_name)
        for msg in messages:
            self.send_message(msg)

    def broadcast(self, contacts: List[str], message: str) -> None:
        """
        Send the same *message* to every contact in *contacts*.
        Opens each chat in sequence.
        """
        logger.info("Broadcasting to %d contacts.", len(contacts))
        for contact in contacts:
            try:
                self.open_chat(contact)
                self.send_message(message)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to message '%s': %s", contact, exc)

    # ── Receiving / reading ──────────────────────────────────────────────────

    def get_last_incoming_message(self) -> Optional[str]:
        """Return the text of the most recent *incoming* message, or None."""
        try:
            el = self.driver.find_element(By.XPATH, Selectors.LAST_MESSAGE_IN)
            return el.text
        except NoSuchElementException:
            return None

    def get_last_outgoing_message(self) -> Optional[str]:
        """Return the text of the most recent *outgoing* message, or None."""
        try:
            el = self.driver.find_element(By.XPATH, Selectors.LAST_MESSAGE_OUT)
            return el.text
        except NoSuchElementException:
            return None

    # ── File / media ─────────────────────────────────────────────────────────

    def send_image(self, image_path: str, caption: str = "") -> None:
        """
        Send an image (or video) file in the currently open chat.
        *image_path* must be an absolute path on the local filesystem.
        """
        abs_path = str(Path(image_path).resolve())
        if not Path(abs_path).exists():
            raise FileNotFoundError(f"Image file not found: {abs_path}")

        logger.info("Attaching image: %s", abs_path)
        attach_btn = self._find(Selectors.ATTACH_BUTTON)
        attach_btn.click()
        time.sleep(0.5)

        file_input = self._find(Selectors.ATTACH_IMAGE_INPUT)
        file_input.send_keys(abs_path)
        time.sleep(1.5)  # wait for preview to load

        if caption:
            # Caption input appears after file selection
            try:
                cap_box = self._wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
                    )
                )
                cap_box.send_keys(caption)
            except TimeoutException:
                logger.warning("Caption box not found; sending without caption.")

        send_btn = self._find(Selectors.SEND_BUTTON)
        send_btn.click()
        time.sleep(self.config.send_delay)
        logger.info("Image sent.")

    # ── Screenshot / debugging ───────────────────────────────────────────────

    def take_screenshot(self, filename: Optional[str] = None) -> str:
        """Save a screenshot and return the path."""
        if filename is None:
            filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        self.driver.save_screenshot(filename)
        logger.info("Screenshot saved: %s", filename)
        return filename

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _find(self, xpath: str):
        """Find element by XPath with the configured timeout."""
        return self._wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def _element_exists(self, xpath: str) -> bool:
        """Return True if at least one element matching *xpath* is in the DOM."""
        try:
            self.driver.find_element(By.XPATH, xpath)
            return True
        except NoSuchElementException:
            return False


# ── Async wrapper ─────────────────────────────────────────────────────────────
class AsyncWhatsAppBot:
    """
    Thin asyncio wrapper around WhatsAppBot.
    Runs blocking Selenium calls in a thread-pool executor so they don't
    block the event loop.

    Example
    -------
    async def main():
        config = BotConfig(firefox_profile_path="/path/to/profile")
        async with AsyncWhatsAppBot(config) as bot:
            await bot.send_message_async("Alice", "Hi from async bot!")
    """

    def __init__(self, config: BotConfig):
        self._bot = WhatsAppBot(config)

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._bot.start)
        return self

    async def __aexit__(self, *_):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._bot.quit)

    async def send_message_async(self, contact: str, message: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._bot.open_chat, contact)
        await loop.run_in_executor(None, self._bot.send_message, message)

    async def broadcast_async(self, contacts: List[str], message: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._bot.broadcast, contacts, message)