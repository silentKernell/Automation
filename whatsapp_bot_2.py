"""
WhatsApp Web Automation Tool — v2
Selectors updated from live WhatsApp Web DOM (April 2026 refresh).
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
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
    StaleElementReferenceException,
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


# ── Selectors (verified against live WhatsApp Web DOM, April 2026) ────────────
class Sel:
    """
    XPath / CSS selectors extracted from real WhatsApp Web HTML.
    WhatsApp uses obfuscated class names that change with updates;
    we prefer aria-label, data-tab, data-testid, and role attributes
    which are far more stable.
    """

    # ── Auth / loading ────────────────────────────────────────────────────────
    # QR code canvas shown when not logged in
    QR_CANVAS          = '//canvas[@aria-label="Scan me!"]'
    # Progress bar shown during initial load
    LOADING_PROGRESS   = '//progress'
    # The left-panel search box — present only when fully loaded and logged in
    # data-tab="3" is the search input (confirmed from live DOM)
    SEARCH_BOX         = '//input[@data-tab="3"]'

    # ── Chat list ─────────────────────────────────────────────────────────────
    # The scrollable chat list grid
    CHAT_LIST_GRID     = '//div[@aria-label="Chat list"][@role="grid"]'
    # A single chat row — match by the span that carries the contact title attr
    CHAT_ROW_BY_NAME   = '//span[@dir="auto"][@title="{name}"]'
    # Unread badge inside a chat row
    UNREAD_BADGE       = './/span[contains(@aria-label,"unread message")]'

    # ── Chat filters (All / Unread / Favorites / Groups tabs) ────────────────
    FILTER_ALL         = '//button[@id="all-filter"]'
    FILTER_UNREAD      = '//button[@id="unread-filter"]'
    FILTER_FAVORITES   = '//button[@id="favorites-filter"]'
    FILTER_GROUPS      = '//button[@id="group-filter"]'

    # ── Message composer ──────────────────────────────────────────────────────
    # data-tab="10" is the message input box (confirmed from live DOM)
    MSG_INPUT          = '//div[@contenteditable="true"][@data-tab="10"]'
    # Send button
    SEND_BTN           = '//button[@data-testid="compose-btn-send"]'

    # ── Received / sent messages in an open chat ──────────────────────────────
    # Incoming message text
    LAST_MSG_IN        = (
        '(//div[contains(@class,"message-in")]'
        '//span[@dir="ltr" or @dir="rtl" or @dir="auto"]'
        '[contains(@class,"selectable-text")])[last()]'
    )
    # Outgoing message text
    LAST_MSG_OUT       = (
        '(//div[contains(@class,"message-out")]'
        '//span[@dir="ltr" or @dir="rtl" or @dir="auto"]'
        '[contains(@class,"selectable-text")])[last()]'
    )

    # ── Attach / media ────────────────────────────────────────────────────────
    ATTACH_BTN         = '//div[@title="Attach"]'
    # File input that accepts images/videos — hidden, send_keys path directly
    ATTACH_IMG_INPUT   = (
        '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]'
    )

    # ── New-chat button (top-right of sidebar) ────────────────────────────────
    # aria-label confirmed from live DOM header
    NEW_CHAT_BTN       = '//button[@aria-label="New chat"]'
    # Contact search box inside the new-chat panel
    NEW_CHAT_SEARCH    = '//p[@class="selectable-text copyable-text"]'


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class BotConfig:
    """All tuneable parameters."""
    # Path to an existing Firefox profile that already has WhatsApp Web logged in.
    #   Linux  : ~/.mozilla/firefox/<profile>.default-release
    #   macOS  : ~/Library/Application Support/Firefox/Profiles/<profile>
    #   Windows: %APPDATA%\Mozilla\Firefox\Profiles\<profile>
    firefox_profile_path: str = "/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr"
    # Optional explicit path to geckodriver binary (leave "" to use PATH)
    geckodriver_path: str = ""
    # Run browser without a visible window
    headless: bool = False
    # Max seconds to wait for any element
    element_timeout: int = 30
    # Max seconds to wait for WhatsApp to finish loading after launch
    load_timeout: int = 60
    # Seconds between consecutive messages (avoids rate-limits)
    send_delay: float = 1.5
    # Extra Firefox preferences dict
    extra_prefs: dict = field(default_factory=dict)


# ── Core bot ──────────────────────────────────────────────────────────────────
class WhatsAppBot:
    """
    Selenium-powered WhatsApp Web automation client.

    Quick start
    -----------
    config = BotConfig(firefox_profile_path="/path/to/your/firefox/profile")
    with WhatsAppBot(config) as bot:
        bot.open_chat("Vickie G")
        bot.send_message("Hello from the bot!")
    """

    WHATSAPP_URL = "https://web.whatsapp.com"

    def __init__(self, config: BotConfig):
        self.config = config
        self.driver: Optional[webdriver.Firefox] = None
        self._wait: Optional[WebDriverWait] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch Firefox, navigate to WhatsApp Web, and wait until ready."""
        logger.info("Starting WhatsApp Web automation …")
        self.driver = self._build_driver()
        self._wait   = WebDriverWait(self.driver, self.config.element_timeout)
        self.driver.get(self.WHATSAPP_URL)
        self._wait_for_load()
        logger.info("WhatsApp Web is ready.")

    def quit(self) -> None:
        if self.driver:
            logger.info("Shutting down browser.")
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.quit()

    # ── Session setup ─────────────────────────────────────────────────────────

    def _build_driver(self) -> webdriver.Firefox:
        options = Options()

        # — Persistent profile (keeps cookies / IndexedDB → stays logged in) —
        profile_path = self.config.firefox_profile_path
        if profile_path:
            if not Path(profile_path).exists():
                raise FileNotFoundError(
                    f"Firefox profile not found: {profile_path}\n"
                    "Run 'firefox -ProfileManager' to list available profiles."
                )
            options.profile = profile_path
            logger.info("Using Firefox profile: %s", profile_path)
        else:
            logger.warning(
                "No firefox_profile_path provided — a temporary profile will "
                "be created. You will need to scan the QR code each run."
            )

        if self.config.headless:
            options.add_argument("--headless")

        # Sensible defaults
        default_prefs = {
            "dom.webnotifications.enabled": False,
            "media.volume_scale": "0.0",
        }
        for k, v in {**default_prefs, **self.config.extra_prefs}.items():
            options.set_preference(k, v)

        service_kwargs = {}
        if self.config.geckodriver_path:
            service_kwargs["executable_path"] = self.config.geckodriver_path
        service = Service(**service_kwargs)

        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(self.config.load_timeout)
        return driver

    def _wait_for_load(self) -> None:
        """
        Wait for WhatsApp Web to either:
          (a) show the main UI (search box)  → already authenticated, OR
          (b) show the QR code canvas        → need to scan.
        """
        logger.info("Waiting up to %ds for WhatsApp Web …", self.config.load_timeout)
        try:
            WebDriverWait(self.driver, self.config.load_timeout).until(
                lambda d: (
                    self._exists(Sel.SEARCH_BOX)
                    or self._exists(Sel.QR_CANVAS)
                )
            )
        except TimeoutException:
            raise TimeoutException(
                f"WhatsApp Web did not load within {self.config.load_timeout}s."
            )

        if self._exists(Sel.QR_CANVAS):
            logger.warning(
                "QR code detected — please scan with your phone. "
                "Waiting up to %ds …", self.config.load_timeout
            )
            WebDriverWait(self.driver, self.config.load_timeout).until(
                EC.presence_of_element_located((By.XPATH, Sel.SEARCH_BOX))
            )
            logger.info("QR code scanned successfully.")

    # ── Chat navigation ───────────────────────────────────────────────────────

    def open_chat(self, contact_name: str) -> None:
        """
        Search for *contact_name* in the sidebar and open the chat.
        The name must match the title attribute of the chat row exactly
        (as it appears in the WhatsApp contact list).
        """
        logger.info("Opening chat: %s", contact_name)

        # Click the search input (data-tab="3" confirmed from live DOM)
        search = self._find(Sel.SEARCH_BOX)
        search.click()
        search.send_keys(Keys.CONTROL + "a")  # clear any existing text
        search.send_keys(Keys.DELETE)
        search.send_keys(contact_name)
        time.sleep(1.2)  # let results render

        row_xpath = Sel.CHAT_ROW_BY_NAME.format(name=contact_name)
        try:
            row = WebDriverWait(self.driver, self.config.element_timeout).until(
                EC.element_to_be_clickable((By.XPATH, row_xpath))
            )
            row.click()
            time.sleep(0.8)
            logger.info("Chat opened: %s", contact_name)
        except TimeoutException:
            # Clear search and raise
            search.send_keys(Keys.ESCAPE)
            raise TimeoutException(
                f"Contact '{contact_name}' not found. "
                "Check that the name matches exactly as shown in WhatsApp."
            )

    def apply_filter(self, filter_name: str = "all") -> None:
        """
        Click one of the chat-list filter tabs.
        filter_name: 'all' | 'unread' | 'favorites' | 'groups'
        """
        mapping = {
            "all":       Sel.FILTER_ALL,
            "unread":    Sel.FILTER_UNREAD,
            "favorites": Sel.FILTER_FAVORITES,
            "groups":    Sel.FILTER_GROUPS,
        }
        xpath = mapping.get(filter_name.lower())
        if not xpath:
            raise ValueError(f"Unknown filter '{filter_name}'. "
                             f"Choose from: {list(mapping)}")
        self._find(xpath).click()
        time.sleep(0.5)
        logger.info("Applied filter: %s", filter_name)

    # ── Messaging ─────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> None:
        """Type and send a plain-text message in the currently open chat."""
        if not text.strip():
            logger.warning("send_message: empty text, skipped.")
            return
        logger.info("Sending: %.60s%s", text, "…" if len(text) > 60 else "")

        box = self._find(Sel.MSG_INPUT)
        box.click()

        # Multi-line support: newlines → Shift+Enter
        lines = text.split("\n")
        for i, line in enumerate(lines):
            box.send_keys(line)
            if i < len(lines) - 1:
                box.send_keys(Keys.SHIFT + Keys.RETURN)

        box.send_keys(Keys.RETURN)
        time.sleep(self.config.send_delay)

    def send_messages_bulk(self, contact: str, messages: List[str]) -> None:
        """Open *contact* and send every message in *messages*."""
        self.open_chat(contact)
        for msg in messages:
            self.send_message(msg)

    def broadcast(self, contacts: List[str], message: str) -> Dict[str, bool]:
        """
        Send *message* to every contact in *contacts*.
        Returns a dict mapping contact name → success (bool).
        """
        results: Dict[str, bool] = {}
        logger.info("Broadcasting to %d contacts …", len(contacts))
        for contact in contacts:
            try:
                self.open_chat(contact)
                self.send_message(message)
                results[contact] = True
            except Exception as exc:
                logger.error("Failed to message '%s': %s", contact, exc)
                results[contact] = False
        return results

    # ── Reading messages ──────────────────────────────────────────────────────

    def get_last_incoming_message(self) -> Optional[str]:
        """Return the text of the most recent received message, or None."""
        try:
            el = self.driver.find_element(By.XPATH, Sel.LAST_MSG_IN)
            return el.text
        except NoSuchElementException:
            return None

    def get_last_outgoing_message(self) -> Optional[str]:
        """Return the text of the most recent sent message, or None."""
        try:
            el = self.driver.find_element(By.XPATH, Sel.LAST_MSG_OUT)
            return el.text
        except NoSuchElementException:
            return None

    def get_unread_chats(self) -> List[str]:
        """
        Scan the currently visible chat list and return names/numbers
        of chats that have an unread-message badge.
        Only chats rendered in the DOM (virtual list) are returned.
        """
        unread = []
        try:
            rows = self.driver.find_elements(
                By.XPATH,
                '//div[@aria-label="Chat list"][@role="grid"]'
                '//div[@role="gridcell"]'
            )
            for row in rows:
                try:
                    # Check for unread badge
                    badges = row.find_elements(
                        By.XPATH,
                        './/span[contains(@aria-label,"unread message")]'
                    )
                    if badges:
                        name_el = row.find_elements(
                            By.XPATH,
                            './/span[@dir="auto"][contains(@class,"x1iyjqo2")]'
                        )
                        if name_el:
                            unread.append(name_el[0].get_attribute("title") or
                                          name_el[0].text)
                except StaleElementReferenceException:
                    continue
        except Exception as exc:
            logger.warning("get_unread_chats error: %s", exc)
        return unread

    # ── Media / file sending ──────────────────────────────────────────────────

    def send_image(self, image_path: str, caption: str = "") -> None:
        """
        Send a local image or video file in the currently open chat.
        *image_path* must be an absolute filesystem path.
        """
        abs_path = str(Path(image_path).resolve())
        if not Path(abs_path).exists():
            raise FileNotFoundError(f"File not found: {abs_path}")

        logger.info("Attaching file: %s", abs_path)
        attach = self._find(Sel.ATTACH_BTN)
        attach.click()
        time.sleep(0.6)

        file_input = self._find(Sel.ATTACH_IMG_INPUT)
        file_input.send_keys(abs_path)
        time.sleep(1.8)  # wait for preview

        if caption:
            try:
                cap = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located(
                        (By.XPATH, Sel.MSG_INPUT)
                    )
                )
                cap.send_keys(caption)
            except TimeoutException:
                logger.warning("Caption input not found; sending without caption.")

        self._find(Sel.SEND_BTN).click()
        time.sleep(self.config.send_delay)
        logger.info("File sent.")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def take_screenshot(self, filename: Optional[str] = None) -> str:
        """Save a PNG screenshot and return its path."""
        if not filename:
            filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        self.driver.save_screenshot(filename)
        logger.info("Screenshot: %s", filename)
        return filename

    def scroll_chat_list(self, pixels: int = 500) -> None:
        """Scroll the chat list pane to load more chats into the virtual DOM."""
        try:
            pane = self.driver.find_element(By.ID, "pane-side")
            self.driver.execute_script(
                "arguments[0].scrollTop += arguments[1]", pane, pixels
            )
            time.sleep(0.5)
        except NoSuchElementException:
            pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _find(self, xpath: str):
        """Wait for and return a single element, raising TimeoutException if absent."""
        return self._wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def _click(self, xpath: str) -> None:
        self._wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        ).click()

    def _exists(self, xpath: str) -> bool:
        try:
            self.driver.find_element(By.XPATH, xpath)
            return True
        except NoSuchElementException:
            return False


# ── Async wrapper ─────────────────────────────────────────────────────────────
class AsyncWhatsAppBot:
    """
    asyncio wrapper — runs blocking Selenium calls in a thread-pool executor
    so they never block the event loop.

    Usage
    -----
    async with AsyncWhatsAppBot(config) as bot:
        await bot.send_message_async("Vickie G", "Hello async!")
    """

    def __init__(self, config: BotConfig):
        self._bot = WhatsAppBot(config)

    async def __aenter__(self):
        await asyncio.get_event_loop().run_in_executor(None, self._bot.start)
        return self

    async def __aexit__(self, *_):
        await asyncio.get_event_loop().run_in_executor(None, self._bot.quit)

    async def open_chat_async(self, contact: str) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None, self._bot.open_chat, contact
        )

    async def send_message_async(self, contact: str, message: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._bot.open_chat, contact)
        await loop.run_in_executor(None, self._bot.send_message, message)

    async def broadcast_async(
        self, contacts: List[str], message: str
    ) -> Dict[str, bool]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._bot.broadcast, contacts, message
        )

    async def get_unread_chats_async(self) -> List[str]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._bot.get_unread_chats
        )

if __name__ == "__main__":
    config = BotConfig()
    with WhatsAppBot(config) as bot:
        bot.open_chat("~Taliban Mkristu")
        bot.send_message("Hello from the bot!")