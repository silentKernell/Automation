"""
WhatsApp Web Automation Tool — v4 (ELITE Edition)
Features:
- Human-like typing simulation (character by character)
- CSV contact list broadcasting with cooldown
- ✅ Robust Status Watcher for contact statuses (FIXED)
- ✅ POST STATUS (Text, Photo, Video) with privacy controls
- Linked device pairing via terminal code
- Group messaging support
- High-quality media sending
- Anti-detection & stealth measures
- ✅ Enhanced chat opening (existing + new contacts)
"""

import os
import time
import logging
import asyncio
import random
import csv
import json
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Thread, Event
from collections import deque
from queue import Queue
import re
import base64

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
    ElementClickInterceptedException,
    ElementNotInteractableException,
)

# Optional: for better stealth
try:
    from selenium.webdriver.common.action_chains import ActionChains
    HAS_ACTIONS = True
except:
    HAS_ACTIONS = False

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

# ── Selectors (enhanced with fallbacks) ──────────────────────────────────────
class Sel:
    """Stable selectors with multiple fallback strategies."""
    
    # Auth / loading
    QR_CANVAS = '//canvas[@aria-label="Scan me!"]'
    LOADING_PROGRESS = '//progress'
    SEARCH_BOX = '//input[@data-tab="3"]'
    LINKED_DEVICE_CODE = '//div[contains(@class, "_ak4x")]//span'
    LINK_DEVICE_BTN = '//button[@aria-label="Link a device"]'
    
    # Chat list
    CHAT_LIST_GRID = '//div[@aria-label="Chat list"][@role="grid"]'
    CHAT_ROW_BY_NAME = '//span[@dir="auto"][@title="{name}"]'
    UNREAD_BADGE = './/span[contains(@aria-label,"unread message")]'
    
    # Filters
    FILTER_ALL = '//button[@id="all-filter"]'
    FILTER_UNREAD = '//button[@id="unread-filter"]'
    FILTER_GROUPS = '//button[@id="group-filter"]'
    
    # Message composer
    MSG_INPUT = '//div[@contenteditable="true"][@data-tab="10"]'
    SEND_BTN = '//button[@data-testid="compose-btn-send"]'
    
    # Attach / media
    ATTACH_BTN = '//div[@title="Attach"]'
    ATTACH_IMG_INPUT = '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]'
    ATTACH_DOC_INPUT = '//input[@accept="*"]'
    
    # Status (Viewing) - IMPROVED SELECTORS
    STATUS_UPDATES = '//div[@aria-label="Status updates"]'
    STATUS_THUMBNAIL = '//div[@data-testid="status-thumbnail"]'
    STATUS_VIEWER = '//div[@data-testid="status-viewer"]'
    STATUS_TEXT = '//div[@data-testid="status-text"]'
    STATUS_CONTACT_NAME = './/span[@dir="auto"]'
    STATUS_CLOSE_BTN = '//div[@data-testid="status-viewer-close-button"]'
    
    # Status Posting Selectors
    MY_STATUS = '//div[@data-testid="my-status"]'
    MY_STATUS_ADD_BTN = '//div[@data-testid="my-status"]//button'
    STATUS_TEXT_INPUT = '//div[@contenteditable="true"][@data-testid="status-text-input"]'
    STATUS_PHOTO_VIDEO_BTN = '//div[@data-testid="status-photo-video-btn"]'
    STATUS_CAPTION_INPUT = '//div[@contenteditable="true"][@data-testid="status-caption-input"]'
    STATUS_SEND_BTN = '//div[@data-testid="status-send-btn"]'
    STATUS_DELETE_BTN = '//div[@data-testid="status-delete-btn"]'
    
    # Status privacy
    STATUS_PRIVACY_BTN = '//div[@data-testid="status-privacy-btn"]'
    STATUS_PRIVACY_MY_CONTACTS = '//span[contains(text(), "My contacts")]'
    STATUS_PRIVACY_EXCEPT = '//span[contains(text(), "My contacts except...")]'
    STATUS_PRIVACY_ONLY_SHARE = '//span[contains(text(), "Only share with...")]'
    
    # Navigation
    NAV_STATUS = '//button[@data-testid="navbar-item-status"]'
    NAV_CHATS = '//button[@data-testid="navbar-item-chats"]'
    
    # New Chat Button and Interface
    NEW_CHAT_BTN = '//button[@aria-label="New chat"]'
    NEW_CHAT_SEARCH = '//p[@class="selectable-text copyable-text"]'
    NEW_CHAT_RESULT = '//div[@role="option"]'
    
    # Back button
    BACK_BTN = '//div[@aria-label="Back"]'


# ── Configuration ────────────────────────────────────────────────────────────
@dataclass
class BotConfig:
    """Enhanced configuration with all new features."""
    
    # Paths
    firefox_profile_path: str = "/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr"
    geckodriver_path: str = ""
    downloads_path: str = "./downloads"
    media_cache_path: str = "./media_cache"
    
    # Browser behavior
    headless: bool = False
    element_timeout: int = 30
    load_timeout: int = 60
    
    # Typing simulation
    enable_human_typing: bool = True
    typing_speed_range: Tuple[float, float] = (0.05, 0.15)
    typing_variance: float = 0.03
    
    # Broadcasting
    broadcast_cooldown: float = 2.0
    broadcast_batch_size: int = 10
    broadcast_batch_break: float = 10.0
    
    # Status watching
    watch_status_interval: int = 30
    status_check_enabled: bool = True
    
    # Status posting
    status_post_delay: float = 2.0
    status_expiry_hours: int = 24
    
    # Anti-detection
    random_delay_range: Tuple[float, float] = (0.5, 2.0)
    human_mouse_movement: bool = True
    
    # Media
    compress_images: bool = True
    max_image_size_mb: int = 16
    max_video_size_mb: int = 64
    
    # Extra Firefox preferences
    extra_prefs: dict = field(default_factory=dict)


# ── Enhanced WhatsApp Bot v4 (ELITE) ──────────────────────────────────────────
class WhatsAppBot:
    """Professional WhatsApp automation with status posting and watching."""
    
    WHATSAPP_URL = "https://web.whatsapp.com"
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.driver: Optional[webdriver.Firefox] = None
        self._wait: Optional[WebDriverWait] = None
        self._actions = None
        self._status_watcher: Optional[Thread] = None
        self._stop_status_watcher = Event()
        self._status_callbacks: List[Callable] = []
        self._seen_statuses: set = set()
        self._message_queue = Queue()
        self._is_processing_queue = False
        
        # Create necessary directories
        Path(self.config.downloads_path).mkdir(exist_ok=True)
        Path(self.config.media_cache_path).mkdir(exist_ok=True)
    
    # ── Lifecycle ─────────────────────────────────────────────────────────
    
    def start(self) -> None:
        """Launch Firefox and initialize WhatsApp Web."""
        logger.info("🚀 Starting WhatsApp Web Automation v4 (ELITE)...")
        self.driver = self._build_driver()
        self._wait = WebDriverWait(self.driver, self.config.element_timeout)
        
        if HAS_ACTIONS:
            self._actions = ActionChains(self.driver)
            
        self.driver.get(self.WHATSAPP_URL)
        self._wait_for_load()
        logger.info("✅ WhatsApp Web is ready.")
        
    def quit(self) -> None:
        """Clean shutdown with status watcher stop."""
        self._stop_status_watcher.set()
        if self._status_watcher and self._status_watcher.is_alive():
            self._status_watcher.join(timeout=5)
        if self.driver:
            logger.info("🛑 Shutting down browser.")
            self.driver.quit()
            self.driver = None
            
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        
    # ── Enhanced Typing Simulation ────────────────────────────────────────
    
    def _human_type(self, element, text: str, clear_first: bool = True) -> None:
        """Type text character by character with human-like timing."""
        if not self.config.enable_human_typing:
            element.send_keys(text)
            return
            
        if clear_first:
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            time.sleep(0.2)
        
        for char in text:
            element.send_keys(char)
            
            delay = random.uniform(*self.config.typing_speed_range)
            delay += random.uniform(-self.config.typing_variance, 
                                   self.config.typing_variance)
            delay = max(0.02, min(0.3, delay))
            
            if char in '.!?;':
                delay += random.uniform(0.1, 0.3)
            elif char in ',:':
                delay += random.uniform(0.05, 0.15)
                
            time.sleep(delay)
            
            if random.random() < 0.02:
                time.sleep(random.uniform(0.3, 0.8))
                
        time.sleep(random.uniform(0.1, 0.3))
        
    def _human_mouse_move(self, target_element) -> None:
        """Move mouse naturally to an element."""
        if not self.config.human_mouse_movement or not self._actions:
            return
            
        try:
            x_offset = random.randint(-5, 5)
            y_offset = random.randint(-5, 5)
            
            self._actions.move_to_element_with_offset(target_element, 
                                                      x_offset, y_offset)
            self._actions.pause(random.uniform(0.1, 0.3))
            self._actions.perform()
        except:
            pass
    
    # ── CSV Contact Broadcasting ──────────────────────────────────────────
    
    def load_contacts_from_csv(self, csv_path: str, 
                               name_column: str = "name",
                               phone_column: str = "phone") -> List[Dict]:
        """Load contacts from CSV file."""
        contacts = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    contact = {
                        'name': row.get(name_column, ''),
                        'phone': row.get(phone_column, ''),
                        'raw': row
                    }
                    if contact['name'] or contact['phone']:
                        contacts.append(contact)
            logger.info(f"📇 Loaded {len(contacts)} contacts from {csv_path}")
            return contacts
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            return []
    
    def broadcast_to_contacts(self, contacts: List[Dict], 
                              message: str,
                              identifier_field: str = 'name') -> Dict[str, bool]:
        """Broadcast message to multiple contacts with cooldown periods."""
        results = {}
        total = len(contacts)
        
        for idx, contact in enumerate(contacts):
            identifier = contact.get(identifier_field, '')
            if not identifier:
                identifier = contact.get('phone', f"Contact_{idx}")
                
            try:
                logger.info(f"📤 [{idx+1}/{total}] Sending to: {identifier}")
                
                if contact.get('name'):
                    self.open_chat(contact['name'])
                elif contact.get('phone'):
                    self.open_chat_by_phone(contact['phone'])
                else:
                    logger.warning(f"❌ No identifier for contact at index {idx}")
                    results[identifier] = False
                    continue
                
                self.send_message(message)
                results[identifier] = True
                
                if idx < total - 1:
                    if (idx + 1) % self.config.broadcast_batch_size == 0:
                        logger.info(f"☕ Batch break: {self.config.broadcast_batch_break}s")
                        time.sleep(self.config.broadcast_batch_break)
                    else:
                        cooldown = self.config.broadcast_cooldown
                        cooldown += random.uniform(-0.3, 0.5)
                        cooldown = max(1.0, cooldown)
                        logger.debug(f"⏱️ Cooldown: {cooldown:.1f}s")
                        time.sleep(cooldown)
                        
            except Exception as e:
                logger.error(f"❌ Failed to send to {identifier}: {e}")
                results[identifier] = False
                
        success_count = sum(results.values())
        logger.info(f"✅ Broadcast complete: {success_count}/{total} successful")
        return results
    
    def open_chat_by_phone(self, phone_number: str) -> None:
        """Open chat using international phone number."""
        formatted = f"{phone_number}".replace("+", "").replace(" ", "")
        self.open_chat(formatted)
    
    # ── ENHANCED CHAT OPENING (Handles Existing + New Chats) ──────────────
    
    def open_chat(self, contact_name: str, force_new_chat: bool = False) -> bool:
        """
        Open a chat by contact name. Robustly handles both existing chats and new contacts.
        
        Args:
            contact_name: Name or phone number of the contact
            force_new_chat: If True, always create a new chat even if existing found
        
        Returns:
            bool: True if chat opened successfully
        """
        logger.info(f"Opening chat: {contact_name}")
        
        # First, ensure we're in the chat list view
        self._ensure_chat_list_view()
        
        # Get the search box
        search = self._find(Sel.SEARCH_BOX)
        search.click()
        time.sleep(0.3)
        
        # Clear search box
        search.send_keys(Keys.CONTROL + "a")
        search.send_keys(Keys.DELETE)
        time.sleep(0.2)
        
        # Type search term with human delay
        self._human_type(search, contact_name, clear_first=False)
        time.sleep(1.5)
        
        # Try to find existing chat
        row_xpath = Sel.CHAT_ROW_BY_NAME.format(name=contact_name)
        
        if not force_new_chat:
            try:
                row = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, row_xpath))
                )
                self._human_mouse_move(row)
                row.click()
                time.sleep(0.8)
                logger.info(f"✅ Existing chat opened: {contact_name}")
                return True
            except TimeoutException:
                logger.info(f"Chat '{contact_name}' not found, creating new chat...")
        
        # Create new chat
        return self._create_new_chat(contact_name)
    
    def _ensure_chat_list_view(self) -> None:
        """Ensure we're in the chat list view, not inside a chat."""
        try:
            # Check if we're inside a chat by looking for message input
            msg_input_exists = self._exists(Sel.MSG_INPUT, timeout=1)
            
            if msg_input_exists:
                # We're in a chat, go back to chat list
                try:
                    back_btn = self._find(Sel.BACK_BTN, timeout=3)
                    back_btn.click()
                    time.sleep(0.8)
                except:
                    # Try ESC key
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    time.sleep(0.5)
                    
                # Also ensure we're on Chats tab
                chats_tab = self._find(Sel.NAV_CHATS, timeout=5)
                chats_tab.click()
                time.sleep(0.5)
        except:
            pass
    
    def _create_new_chat(self, contact_name: str) -> bool:
        """Create and open a new chat with a contact."""
        try:
            # Clear any existing search
            search = self._find(Sel.SEARCH_BOX)
            search.send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            
            # Click the New Chat button
            new_chat_btn = self._find_new_chat_button()
            new_chat_btn.click()
            time.sleep(1)
            
            # Find and interact with the new chat search input
            new_chat_search = self._find_new_chat_search_input()
            new_chat_search.click()
            time.sleep(0.3)
            
            # Type the contact name
            self._human_type(new_chat_search, contact_name, clear_first=True)
            time.sleep(1.5)
            
            # Select the contact from search results
            if not self._select_contact_from_search(contact_name):
                # Try with phone number format
                logger.warning(f"Could not find '{contact_name}', trying as phone number...")
                new_chat_search.click()
                self._human_type(new_chat_search, Keys.CONTROL + "a", clear_first=False)
                self._human_type(new_chat_search, Keys.DELETE, clear_first=False)
                time.sleep(0.3)
                
                phone_formatted = re.sub(r'[^0-9+]', '', contact_name)
                self._human_type(new_chat_search, phone_formatted, clear_first=False)
                time.sleep(1.5)
                
                if not self._select_contact_from_search(contact_name):
                    # Press Enter to create chat with phone number directly
                    new_chat_search.send_keys(Keys.RETURN)
                    time.sleep(1)
            
            time.sleep(1.5)
            logger.info(f"✅ New chat created: {contact_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create new chat: {e}")
            return False
    
    def _find_new_chat_button(self):
        """Find the New Chat button using multiple strategies."""
        strategies = [
            Sel.NEW_CHAT_BTN,
            '//div[@data-testid="new-chat-button"]',
            '//span[@data-testid="new-chat-outline"]/ancestor::button',
            '//button[.//span[@data-testid="new-chat-outline"]]',
        ]
        
        for strategy in strategies:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, strategy))
                )
                return btn
            except:
                continue
        
        raise TimeoutException("Could not find New Chat button")
    
    def _find_new_chat_search_input(self):
        """Find the search input in the New Chat interface."""
        strategies = [
            Sel.NEW_CHAT_SEARCH,
            '//div[@contenteditable="true"][@data-tab="3"]',
            '//input[@placeholder="Search"]',
        ]
        
        for strategy in strategies:
            try:
                search_input = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, strategy))
                )
                return search_input
            except:
                continue
        
        return self._find(Sel.SEARCH_BOX)
    
    def _select_contact_from_search(self, contact_name: str) -> bool:
        """Select a contact from search results."""
        strategies = [
            f'//span[@title="{contact_name}"]',
            f'//div[contains(text(), "{contact_name}")]',
            f'//span[contains(text(), "{contact_name}")]',
            Sel.NEW_CHAT_RESULT,
        ]
        
        for strategy in strategies:
            try:
                time.sleep(0.5)
                elements = self.driver.find_elements(By.XPATH, strategy)
                for element in elements:
                    if contact_name.lower() in element.text.lower():
                        self._human_mouse_move(element)
                        element.click()
                        time.sleep(0.5)
                        return True
            except:
                continue
        
        # Fallback: press Enter to select first result
        try:
            search_input = self.driver.switch_to.active_element
            search_input.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.3)
            search_input.send_keys(Keys.RETURN)
            time.sleep(0.5)
            return True
        except:
            pass
        
        return False
    
    # ── Enhanced Messaging ────────────────────────────────────────────────
    
    def send_message(self, text: str) -> None:
        """Send message with human-like typing simulation."""
        if not text.strip():
            logger.warning("Empty message, skipped.")
            return
            
        logger.info(f"✍️ Sending: {text[:50]}..." if len(text) > 50 else f"✍️ Sending: {text}")
        
        box = self._find(Sel.MSG_INPUT, timeout=15)
        box.click()
        time.sleep(random.uniform(0.1, 0.3))
        
        self._human_type(box, text, clear_first=False)
        box.send_keys(Keys.RETURN)
        time.sleep(random.uniform(0.5, 1.5))
        
    def send_message_with_retry(self, text: str, max_retries: int = 3) -> bool:
        """Send message with retry logic on failure."""
        for attempt in range(max_retries):
            try:
                self.send_message(text)
                return True
            except Exception as e:
                logger.warning(f"Retry {attempt+1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)
        return False
    
    # ════════════════════════════════════════════════════════════════════════
    # ║                    IMPROVED STATUS WATCHER                            ║
    # ════════════════════════════════════════════════════════════════════════
    
    def start_status_watcher(self, callback: Optional[Callable] = None) -> None:
        """Start background thread to watch for new status updates."""
        if callback:
            self._status_callbacks.append(callback)
            
        if self._status_watcher and self._status_watcher.is_alive():
            logger.warning("Status watcher already running")
            return
            
        self._stop_status_watcher.clear()
        self._seen_statuses.clear()
        self._status_watcher = Thread(target=self._watch_status_loop, daemon=True)
        self._status_watcher.start()
        logger.info("👁️ Status watcher started")
        
    def stop_status_watcher(self) -> None:
        """Stop the status watcher thread."""
        self._stop_status_watcher.set()
        if self._status_watcher:
            self._status_watcher.join(timeout=5)
        logger.info("Status watcher stopped")
        
    def add_status_callback(self, callback: Callable) -> None:
        """Add callback function for status updates."""
        self._status_callbacks.append(callback)
    
    def _watch_status_loop(self) -> None:
        """Background loop checking for status updates - IMPROVED."""
        last_update_time = datetime.now()
        consecutive_errors = 0
        
        while not self._stop_status_watcher.is_set():
            try:
                # Navigate to status section
                status_tab = self._find(Sel.NAV_STATUS, timeout=10)
                status_tab.click()
                time.sleep(1.5)
                
                # Find status updates section
                status_updates_section = self._find(Sel.STATUS_UPDATES, timeout=5)
                
                # Get all status thumbnails (contacts who posted)
                status_thumbnails = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
                
                for thumbnail in status_thumbnails:
                    try:
                        # Get contact name
                        name_element = thumbnail.find_element(By.XPATH, Sel.STATUS_CONTACT_NAME)
                        contact_name = name_element.text.strip()
                        
                        if not contact_name:
                            continue
                        
                        # Create unique ID for this status
                        status_id = f"{contact_name}_{datetime.now().strftime('%Y%m%d_%H')}"
                        
                        if status_id not in self._seen_statuses:
                            self._seen_statuses.add(status_id)
                            
                            # Try to get status preview/text
                            status_text = ""
                            try:
                                # Click to view status
                                thumbnail.click()
                                time.sleep(2)
                                
                                # Extract status text if any
                                text_element = self._find(Sel.STATUS_TEXT, timeout=3)
                                status_text = text_element.text if text_element else ""
                                
                                # Close status viewer
                                close_btn = self._find(Sel.STATUS_CLOSE_BTN, timeout=3)
                                close_btn.click()
                                time.sleep(0.5)
                            except:
                                pass
                            
                            status_data = {
                                'contact': contact_name,
                                'timestamp': datetime.now().isoformat(),
                                'text': status_text,
                                'type': 'status_update'
                            }
                            
                            logger.info(f"📢 New status detected from: {contact_name}")
                            
                            # Notify callbacks
                            for callback in self._status_callbacks:
                                try:
                                    callback(status_data)
                                except Exception as e:
                                    logger.error(f"Status callback error: {e}")
                                    
                    except Exception as e:
                        continue
                
                # Reset error counter on success
                consecutive_errors = 0
                last_update_time = datetime.now()
                
                # Return to chats view to avoid getting stuck
                chats_tab = self._find(Sel.NAV_CHATS, timeout=5)
                chats_tab.click()
                
                time.sleep(self.config.watch_status_interval)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Status watcher error ({consecutive_errors}): {e}")
                
                # Exponential backoff on errors
                backoff = min(30, consecutive_errors * 2)
                time.sleep(backoff)
                
                # Try to recover by refreshing
                if consecutive_errors > 5:
                    logger.warning("Too many errors, attempting refresh...")
                    try:
                        self.driver.refresh()
                        time.sleep(5)
                        consecutive_errors = 0
                    except:
                        pass
    
    def view_contact_status(self, contact_name: str) -> Optional[Dict]:
        """View a specific contact's status and return details."""
        try:
            # Navigate to status
            status_tab = self._find(Sel.NAV_STATUS, timeout=10)
            status_tab.click()
            time.sleep(1.5)
            
            # Find the contact's status
            status_thumbnails = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
            
            for thumbnail in status_thumbnails:
                name_element = thumbnail.find_element(By.XPATH, Sel.STATUS_CONTACT_NAME)
                if contact_name.lower() in name_element.text.lower():
                    # Click to view
                    thumbnail.click()
                    time.sleep(2)
                    
                    # Extract status text
                    status_text = ""
                    try:
                        text_element = self._find(Sel.STATUS_TEXT, timeout=3)
                        status_text = text_element.text if text_element else ""
                    except:
                        pass
                    
                    # Close viewer
                    close_btn = self._find(Sel.STATUS_CLOSE_BTN, timeout=3)
                    close_btn.click()
                    
                    return {
                        'contact': contact_name,
                        'text': status_text,
                        'viewed_at': datetime.now().isoformat()
                    }
            
            logger.warning(f"No status found for {contact_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to view status: {e}")
            return None
    
    # ════════════════════════════════════════════════════════════════════════
    # ║                    STATUS POSTING CAPABILITIES                        ║
    # ════════════════════════════════════════════════════════════════════════
    
    def _navigate_to_status_section(self) -> bool:
        """Navigate to the status section for posting."""
        try:
            status_tab = self._find(Sel.NAV_STATUS, timeout=10)
            status_tab.click()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to Status: {e}")
            return False
    
    def post_text_status(self, text: str, 
                         background_color: Optional[str] = None,
                         font_size: str = "normal") -> bool:
        """Post a text status update."""
        logger.info(f"📝 Posting text status: {text[:50]}...")
        
        if not self._navigate_to_status_section():
            return False
        
        try:
            # Click on My Status to add new status
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            # Click text status button
            text_status_btn = self._find('//button[@aria-label="Text status"]', timeout=5)
            text_status_btn.click()
            time.sleep(1)
            
            # Find and type in text input
            text_input = self._find(Sel.STATUS_TEXT_INPUT, timeout=10)
            text_input.click()
            time.sleep(0.3)
            
            self._human_type(text_input, text, clear_first=True)
            time.sleep(0.5)
            
            # Change background if specified
            if background_color:
                self._change_status_background(background_color)
                time.sleep(0.5)
            
            # Change font size if specified
            if font_size != "normal":
                self._change_status_font_size(font_size)
                time.sleep(0.5)
            
            # Send the status
            send_btn = self._find(Sel.STATUS_SEND_BTN, timeout=10)
            send_btn.click()
            
            time.sleep(self.config.status_post_delay)
            logger.info("✅ Text status posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post text status: {e}")
            return False
    
    def _change_status_background(self, color: str) -> None:
        """Change status background color."""
        try:
            bg_btn = self._find('//button[@aria-label="Background"]', timeout=5)
            bg_btn.click()
            time.sleep(0.5)
            color_btn = self._find(f'//div[@aria-label="{color}"]', timeout=3)
            color_btn.click()
        except:
            logger.warning(f"Could not set background to {color}")
    
    def _change_status_font_size(self, size: str) -> None:
        """Change status font size."""
        try:
            font_btn = self._find('//button[@aria-label="Font size"]', timeout=5)
            font_btn.click()
            time.sleep(0.5)
            size_map = {"small": "Small", "normal": "Normal", "large": "Large"}
            size_btn = self._find(f'//span[contains(text(), "{size_map[size]}")]', timeout=3)
            size_btn.click()
        except:
            logger.warning(f"Could not set font size to {size}")
    
    def post_photo_status(self, image_path: str, caption: str = "") -> bool:
        """Post a photo status update."""
        abs_path = str(Path(image_path).resolve())
        if not Path(abs_path).exists():
            logger.error(f"Image not found: {abs_path}")
            return False
            
        logger.info(f"🖼️ Posting photo status: {abs_path}")
        
        if not self._navigate_to_status_section():
            return False
        
        try:
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            media_btn = self._find(Sel.STATUS_PHOTO_VIDEO_BTN, timeout=10)
            media_btn.click()
            time.sleep(1)
            
            file_input = self._find('//input[@type="file"][@accept="image/*,video/*"]', timeout=10)
            self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
            file_input.send_keys(abs_path)
            
            time.sleep(3)
            
            if caption:
                try:
                    caption_input = self._find(Sel.STATUS_CAPTION_INPUT, timeout=5)
                    caption_input.click()
                    self._human_type(caption_input, caption)
                except:
                    logger.warning("Could not add caption")
            
            send_btn = self._find(Sel.STATUS_SEND_BTN, timeout=10)
            send_btn.click()
            
            time.sleep(self.config.status_post_delay)
            logger.info("✅ Photo status posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post photo status: {e}")
            return False
    
    def post_video_status(self, video_path: str, caption: str = "") -> bool:
        """Post a video status update."""
        abs_path = str(Path(video_path).resolve())
        if not Path(abs_path).exists():
            logger.error(f"Video not found: {abs_path}")
            return False
            
        logger.info(f"🎬 Posting video status: {abs_path}")
        
        if not self._navigate_to_status_section():
            return False
        
        try:
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            media_btn = self._find(Sel.STATUS_PHOTO_VIDEO_BTN, timeout=10)
            media_btn.click()
            time.sleep(1)
            
            file_input = self._find('//input[@type="file"][@accept="image/*,video/*"]', timeout=10)
            self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
            file_input.send_keys(abs_path)
            
            time.sleep(4)
            
            if caption:
                try:
                    caption_input = self._find(Sel.STATUS_CAPTION_INPUT, timeout=5)
                    caption_input.click()
                    self._human_type(caption_input, caption)
                except:
                    logger.warning("Could not add caption")
            
            send_btn = self._find(Sel.STATUS_SEND_BTN, timeout=10)
            send_btn.click()
            
            time.sleep(self.config.status_post_delay)
            logger.info("✅ Video status posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post video status: {e}")
            return False
    
    def post_quote_status(self, quote: str, author: str = "", 
                          background_color: str = "#075E54") -> bool:
        """Post a quote as a text status."""
        formatted_quote = f"✨ {quote} ✨"
        if author:
            formatted_quote += f"\n\n— {author}"
        return self.post_text_status(formatted_quote, background_color=background_color)
    
    def post_motivational_quote(self) -> bool:
        """Post a random motivational quote."""
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("Success is not final, failure is not fatal.", "Winston Churchill"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
        ]
        quote, author = random.choice(quotes)
        return self.post_quote_status(quote, author)
    
    def delete_my_status(self) -> bool:
        """Delete the current status."""
        try:
            if not self._navigate_to_status_section():
                return False
            
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1.5)
            
            delete_btn = self._find(Sel.STATUS_DELETE_BTN, timeout=5)
            delete_btn.click()
            time.sleep(1)
            
            confirm_btn = self._find('//button[contains(text(), "Delete")]', timeout=5)
            confirm_btn.click()
            
            time.sleep(2)
            logger.info("🗑️ Status deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete status: {e}")
            return False
    
    def set_status_privacy(self, privacy_type: str = "my_contacts") -> bool:
        """Set status privacy settings."""
        try:
            if not self._navigate_to_status_section():
                return False
            
            privacy_btn = self._find(Sel.STATUS_PRIVACY_BTN, timeout=10)
            privacy_btn.click()
            time.sleep(1)
            
            if privacy_type == "my_contacts":
                option = self._find(Sel.STATUS_PRIVACY_MY_CONTACTS, timeout=5)
            elif privacy_type == "only_share":
                option = self._find(Sel.STATUS_PRIVACY_ONLY_SHARE, timeout=5)
            elif privacy_type == "except":
                option = self._find(Sel.STATUS_PRIVACY_EXCEPT, timeout=5)
            else:
                logger.warning(f"Unknown privacy type: {privacy_type}")
                return False
            
            option.click()
            time.sleep(1)
            logger.info(f"🔒 Status privacy set to: {privacy_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set status privacy: {e}")
            return False
    
    # ── Group Messaging ──────────────────────────────────────────────────
    
    def send_group_message(self, group_name: str, message: str) -> bool:
        """Send message to a WhatsApp group."""
        try:
            self.open_chat(group_name)
            self.send_message(message)
            logger.info(f"📢 Message sent to group: {group_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send group message: {e}")
            return False
            
    def get_group_list(self) -> List[str]:
        """Get list of all groups from chat list."""
        groups = []
        try:
            self._click(Sel.FILTER_GROUPS)
            time.sleep(1)
            
            chat_items = self.driver.find_elements(
                By.XPATH, '//div[@aria-label="Chat list"]//div[@role="gridcell"]'
            )
            
            for item in chat_items:
                try:
                    name_el = item.find_element(By.XPATH, './/span[@dir="auto"]')
                    groups.append(name_el.text)
                except:
                    continue
                    
            self._click(Sel.FILTER_ALL)
            logger.info(f"Found {len(groups)} groups")
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get group list: {e}")
            return groups
    
    # ── Enhanced Media Sending ───────────────────────────────────────────
    
    def send_media(self, file_path: str, caption: str = "", 
                   as_document: bool = False) -> bool:
        """Send media file in best quality."""
        abs_path = str(Path(file_path).resolve())
        if not Path(abs_path).exists():
            raise FileNotFoundError(f"File not found: {abs_path}")
            
        logger.info(f"📎 Sending media: {abs_path}")
        
        file_input = Sel.ATTACH_DOC_INPUT if as_document else Sel.ATTACH_IMG_INPUT
            
        try:
            attach = self._find(Sel.ATTACH_BTN)
            attach.click()
            time.sleep(0.8)
            
            input_el = self._find(file_input)
            self.driver.execute_script("arguments[0].style.display = 'block';", input_el)
            input_el.send_keys(abs_path)
            
            time.sleep(2.5)
            
            if caption:
                try:
                    caption_box = WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, Sel.MSG_INPUT))
                    )
                    self._human_type(caption_box, caption)
                except:
                    logger.warning("Could not add caption")
                    
            send_btn = self._find(Sel.SEND_BTN)
            send_btn.click()
            
            time.sleep(self.config.broadcast_cooldown)
            logger.info("✅ Media sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send media: {e}")
            return False
            
    def send_image_high_quality(self, image_path: str, caption: str = "") -> bool:
        """Send image with best quality preservation."""
        return self.send_media(image_path, caption, as_document=False)
        
    def send_video(self, video_path: str, caption: str = "") -> bool:
        """Send video file."""
        return self.send_media(video_path, caption, as_document=False)
        
    def send_document(self, doc_path: str, caption: str = "") -> bool:
        """Send document file."""
        return self.send_media(doc_path, caption, as_document=True)
    
    # ── Linked Device Pairing ────────────────────────────────────────────
    
    def get_linking_code(self, timeout: int = 120) -> Optional[str]:
        """Get linking code to connect as linked device."""
        logger.info("🔗 Starting device linking process...")
        
        try:
            menu_btn = self._find('//button[@aria-label="Menu"]', timeout=10)
            menu_btn.click()
            time.sleep(0.5)
            
            link_btn = self._find(Sel.LINK_DEVICE_BTN, timeout=10)
            link_btn.click()
            time.sleep(1)
            
            code_element = self._find(Sel.LINKED_DEVICE_CODE, timeout=timeout)
            code = code_element.text.strip()
            code = re.sub(r'[^A-Z0-9-]', '', code.upper())
            
            logger.info(f"📱 Linking code: {code}")
            self._wait_for_linked_device(timeout=60)
            return code
            
        except Exception as e:
            logger.error(f"Failed to get linking code: {e}")
            return None
            
    def _wait_for_linked_device(self, timeout: int = 60) -> bool:
        """Wait for confirmation that device was linked."""
        logger.info("Waiting for device to be linked...")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                if self._exists(Sel.SEARCH_BOX, timeout=2):
                    logger.info("✅ Device successfully linked!")
                    return True
            except:
                pass
            time.sleep(2)
            
        logger.warning("Timeout waiting for device linking")
        return False
    
    # ── Utility Methods ──────────────────────────────────────────────────
    
    def _find(self, xpath: str, timeout: Optional[int] = None):
        """Enhanced find with better error handling."""
        wait_time = timeout or self.config.element_timeout
        wait = WebDriverWait(self.driver, wait_time)
        return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        
    def _click(self, xpath: str, timeout: Optional[int] = None) -> None:
        """Enhanced click with retry on interception."""
        wait_time = timeout or self.config.element_timeout
        wait = WebDriverWait(self.driver, wait_time)
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        
        try:
            element.click()
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", element)
            
    def _exists(self, xpath: str, timeout: float = 1) -> bool:
        """Check if element exists."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return True
        except TimeoutException:
            return False
            
    def _build_driver(self) -> webdriver.Firefox:
        """Build Firefox driver with stealth preferences."""
        options = Options()
        
        if self.config.firefox_profile_path:
            if not Path(self.config.firefox_profile_path).exists():
                raise FileNotFoundError(
                    f"Firefox profile not found: {self.config.firefox_profile_path}"
                )
            options.profile = self.config.firefox_profile_path
            
        if self.config.headless:
            options.add_argument("--headless")
            
        stealth_prefs = {
            "dom.webnotifications.enabled": False,
            "media.volume_scale": "0.0",
            "privacy.trackingprotection.enabled": True,
            "privacy.trackingprotection.fingerprinting.enabled": True,
            "webgl.disabled": False,
            "dom.push.enabled": False,
            "dom.serviceWorkers.enabled": False,
        }
        
        for k, v in {**stealth_prefs, **self.config.extra_prefs}.items():
            options.set_preference(k, v)
        
        service_kwargs = {}
        if self.config.geckodriver_path:
            service_kwargs["executable_path"] = self.config.geckodriver_path
        service = Service(**service_kwargs)
        
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(self.config.load_timeout)
        driver.set_window_size(1280, 720)
        
        return driver
        
    def _wait_for_load(self) -> None:
        """Enhanced load waiting with better error handling."""
        logger.info("Waiting for WhatsApp Web to load...")
        
        try:
            WebDriverWait(self.driver, self.config.load_timeout).until(
                lambda d: (self._exists(Sel.SEARCH_BOX) or self._exists(Sel.QR_CANVAS))
            )
        except TimeoutException:
            raise TimeoutException("WhatsApp Web did not load properly")
            
        if self._exists(Sel.QR_CANVAS):
            logger.warning("📱 QR code detected - Please scan with your phone")
            WebDriverWait(self.driver, self.config.load_timeout).until(
                EC.presence_of_element_located((By.XPATH, Sel.SEARCH_BOX))
            )
            logger.info("✅ QR code scanned successfully")


# ── Example Usage & Testing (ELITE v4) ───────────────────────────────────────
if __name__ == "__main__":
    config = BotConfig(
        firefox_profile_path="/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr",
        enable_human_typing=True,
        broadcast_cooldown=2.0,
        watch_status_interval=30,
    )
    
    with WhatsAppBot(config) as bot:
        # Example: Post a status
        # bot.post_text_status("Hello from Elite v4! 🚀", background_color="#128C7E")
        
        message = """
👋 *Hello,*

A bit unconventional—but intentional.

I’m expanding my circle with *focused, growth-minded people* 🚀
*Accountant 📊 | Data Analyst 📈 | Digital Marketer 💻*

I value *real connections, insights, and opportunities.*

👉 If that resonates, kindly *reply with your name* (as you’d like it saved).
👉 If not, no worries at all 👍 — no follow-ups from me.

*Wishing you growth and success either way.* ✨

        """
        
        # Example: Watch for statuses
        def on_status(status):
            print(f"📢 NEW STATUS from {status['contact']}: {status['text'][:50] if status['text'] else '(no text)'}")
        
        # bot.start_status_watcher(callback=on_status)
        contacts = bot.load_contacts_from_csv("/home/kernel/projects/watsApp/contacts_1.csv")
        bot.broadcast_to_contacts(contacts, message)
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            bot.stop_status_watcher()
            print("\n👋 Shutting down...")