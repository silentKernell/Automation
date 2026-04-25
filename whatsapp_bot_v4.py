"""
WhatsApp Web Automation Tool — v4 (ELITE Edition)
Features:
- Human-like typing simulation (character by character)
- CSV contact list broadcasting with cooldown
- Status watcher for contact statuses
- ✅ POST STATUS (Text, Photo, Video) ← NEW
- Linked device pairing via terminal code
- Group messaging support
- High-quality media sending
- Anti-detection & stealth measures
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
    
    # Status (Viewing)
    STATUS_UPDATES = '//div[@aria-label="Status updates"]'
    STATUS_THUMBNAIL = '//div[@data-testid="status-thumbnail"]'
    STATUS_VIEWER = '//div[@data-testid="status-viewer"]'
    STATUS_TEXT = '//div[@data-testid="status-text"]'
    STATUS_MUTE_BTN = '//button[@aria-label="Mute status updates"]'
    
    # ── NEW: Status Posting Selectors ──────────────────────────────────────
    # My Status section (for posting)
    MY_STATUS = '//div[@data-testid="my-status"]'
    MY_STATUS_ADD_BTN = '//div[@data-testid="my-status"]//button'
    MY_STATUS_TEXT = '//div[@data-testid="my-status-text"]'
    
    # Status composer
    STATUS_COMPOSER = '//div[@data-testid="status-composer"]'
    STATUS_TEXT_INPUT = '//div[@contenteditable="true"][@data-testid="status-text-input"]'
    STATUS_PHOTO_VIDEO_BTN = '//div[@data-testid="status-photo-video-btn"]'
    STATUS_CAPTION_INPUT = '//div[@contenteditable="true"][@data-testid="status-caption-input"]'
    STATUS_SEND_BTN = '//div[@data-testid="status-send-btn"]'
    STATUS_DELETE_BTN = '//div[@data-testid="status-delete-btn"]'
    
    # Status privacy
    STATUS_PRIVACY_BTN = '//div[@data-testid="status-privacy-btn"]'
    STATUS_PRIVACY_OPTIONS = '//div[@role="menuitem"]'
    STATUS_PRIVACY_MY_CONTACTS = '//span[contains(text(), "My contacts")]'
    STATUS_PRIVACY_EXCEPT = '//span[contains(text(), "My contacts except...")]'
    STATUS_PRIVACY_ONLY_SHARE = '//span[contains(text(), "Only share with...")]'
    
    # Status media preview
    STATUS_PREVIEW_IMAGE = '//div[@data-testid="status-preview-image"]'
    STATUS_PREVIEW_VIDEO = '//div[@data-testid="status-preview-video"]'
    
    # Groups
    GROUP_INFO = '//div[@data-testid="conversation-panel-header"]'
    GROUP_MEMBERS = '//div[@data-testid="group-members"]'
    
    # New chat
    NEW_CHAT_BTN = '//button[@aria-label="New chat"]'
    NEW_CHAT_SEARCH = '//p[@class="selectable-text copyable-text"]'
    
    # Navigation
    NAV_STATUS = '//button[@data-testid="navbar-item-status"]'


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
    status_expiry_hours: int = 24  # Status auto-expires after 24 hours
    
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
    """
    Professional WhatsApp automation with all requested features including
    status posting capabilities (text, photo, video).
    """
    
    WHATSAPP_URL = "https://web.whatsapp.com"
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.driver: Optional[webdriver.Firefox] = None
        self._wait: Optional[WebDriverWait] = None
        self._actions = None
        self._status_watcher: Optional[Thread] = None
        self._stop_status_watcher = Event()
        self._status_callbacks: List[Callable] = []
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
        
        for i, char in enumerate(text):
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
            rect = target_element.rect
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
    
    # ── Enhanced Messaging ────────────────────────────────────────────────
    
    def send_message(self, text: str) -> None:
        """Send message with human-like typing simulation."""
        if not text.strip():
            logger.warning("Empty message, skipped.")
            return
            
        logger.info(f"✍️ Typing: {text[:50]}..." if len(text) > 50 else f"✍️ Sending: {text}")
        
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
    # ║                    NEW: STATUS POSTING CAPABILITIES                    ║
    # ════════════════════════════════════════════════════════════════════════
    
    def _navigate_to_status(self) -> bool:
        """Navigate to the status section."""
        try:
            # Click on Status tab in navigation
            status_tab = self._find(Sel.NAV_STATUS, timeout=10)
            status_tab.click()
            time.sleep(1.5)
            logger.info("📱 Navigated to Status section")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to Status: {e}")
            return False
    
    def post_text_status(self, text: str, 
                         background_color: Optional[str] = None,
                         font_size: str = "normal") -> bool:
        """
        Post a text status update.
        
        Args:
            text: Status text content
            background_color: Optional background color (e.g., "#FF0000" or "blue")
            font_size: "small", "normal", or "large"
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"📝 Posting text status: {text[:50]}...")
        
        if not self._navigate_to_status():
            return False
        
        try:
            # Find and click on My Status area to add new status
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            # Find text status button
            text_status_btn = self._find('//button[@aria-label="Text status"]', timeout=5)
            text_status_btn.click()
            time.sleep(1)
            
            # Find the text input area
            text_input = self._find(Sel.STATUS_TEXT_INPUT, timeout=10)
            text_input.click()
            time.sleep(0.3)
            
            # Type the status text with human-like typing
            self._human_type(text_input, text, clear_first=True)
            time.sleep(0.5)
            
            # Change background color if specified
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
            
            # Try to find color by value or aria-label
            color_btn = self._find(f'//div[@aria-label="{color}"]', timeout=3)
            color_btn.click()
            time.sleep(0.3)
        except:
            logger.warning(f"Could not set background color to {color}")
    
    def _change_status_font_size(self, size: str) -> None:
        """Change status font size."""
        try:
            font_btn = self._find('//button[@aria-label="Font size"]', timeout=5)
            font_btn.click()
            time.sleep(0.5)
            
            size_map = {"small": "Small", "normal": "Normal", "large": "Large"}
            size_btn = self._find(f'//span[contains(text(), "{size_map[size]}")]', timeout=3)
            size_btn.click()
            time.sleep(0.3)
        except:
            logger.warning(f"Could not set font size to {size}")
    
    def post_photo_status(self, image_path: str, caption: str = "") -> bool:
        """
        Post a photo status update.
        
        Args:
            image_path: Path to the image file
            caption: Optional caption text
        
        Returns:
            bool: True if successful, False otherwise
        """
        abs_path = str(Path(image_path).resolve())
        if not Path(abs_path).exists():
            logger.error(f"Image not found: {abs_path}")
            return False
            
        logger.info(f"🖼️ Posting photo status: {abs_path}")
        
        if not self._navigate_to_status():
            return False
        
        try:
            # Click on My Status to add new status
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            # Find and click the photo/video button
            media_btn = self._find(Sel.STATUS_PHOTO_VIDEO_BTN, timeout=10)
            media_btn.click()
            time.sleep(1)
            
            # Find file input and upload image
            file_input = self._find('//input[@type="file"][@accept="image/*,video/*"]', timeout=10)
            
            # Make input visible if hidden
            self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
            file_input.send_keys(abs_path)
            
            # Wait for upload and preview
            time.sleep(3)
            
            # Add caption if provided
            if caption:
                try:
                    caption_input = self._find(Sel.STATUS_CAPTION_INPUT, timeout=5)
                    caption_input.click()
                    self._human_type(caption_input, caption)
                    time.sleep(0.5)
                except:
                    logger.warning("Could not add caption")
            
            # Send status
            send_btn = self._find(Sel.STATUS_SEND_BTN, timeout=10)
            send_btn.click()
            
            time.sleep(self.config.status_post_delay)
            logger.info("✅ Photo status posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post photo status: {e}")
            return False
    
    def post_video_status(self, video_path: str, caption: str = "") -> bool:
        """
        Post a video status update (max 60 seconds as per WhatsApp).
        
        Args:
            video_path: Path to the video file
            caption: Optional caption text
        
        Returns:
            bool: True if successful, False otherwise
        """
        abs_path = str(Path(video_path).resolve())
        if not Path(abs_path).exists():
            logger.error(f"Video not found: {abs_path}")
            return False
            
        # Check video size
        video_size_mb = Path(abs_path).stat().st_size / (1024 * 1024)
        if video_size_mb > self.config.max_video_size_mb:
            logger.warning(f"Video size ({video_size_mb:.1f}MB) exceeds recommended limit")
        
        logger.info(f"🎬 Posting video status: {abs_path}")
        
        if not self._navigate_to_status():
            return False
        
        try:
            # Click on My Status to add new status
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1)
            
            # Find and click the photo/video button
            media_btn = self._find(Sel.STATUS_PHOTO_VIDEO_BTN, timeout=10)
            media_btn.click()
            time.sleep(1)
            
            # Find file input and upload video
            file_input = self._find('//input[@type="file"][@accept="image/*,video/*"]', timeout=10)
            self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
            file_input.send_keys(abs_path)
            
            # Wait for upload and preview
            time.sleep(4)
            
            # Add caption if provided
            if caption:
                try:
                    caption_input = self._find(Sel.STATUS_CAPTION_INPUT, timeout=5)
                    caption_input.click()
                    self._human_type(caption_input, caption)
                    time.sleep(0.5)
                except:
                    logger.warning("Could not add caption")
            
            # Send status
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
        """
        Post a quote as a text status with nice formatting.
        
        Args:
            quote: The quote text
            author: Quote author (optional)
            background_color: Background color
        
        Returns:
            bool: True if successful
        """
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
            ("Dream it. Wish it. Do it.", ""),
            ("Your limitation—it’s only your imagination.", ""),
            ("Push yourself, because no one else is going to do it for you.", ""),
        ]
        quote, author = random.choice(quotes)
        return self.post_quote_status(quote, author)
    
    def delete_my_status(self) -> bool:
        """Delete the currently displayed my status."""
        try:
            if not self._navigate_to_status():
                return False
            
            # Click on My Status to view
            my_status = self._find(Sel.MY_STATUS, timeout=10)
            my_status.click()
            time.sleep(1.5)
            
            # Find and click delete button
            delete_btn = self._find(Sel.STATUS_DELETE_BTN, timeout=5)
            delete_btn.click()
            time.sleep(1)
            
            # Confirm deletion
            confirm_btn = self._find('//button[contains(text(), "Delete")]', timeout=5)
            confirm_btn.click()
            
            time.sleep(2)
            logger.info("🗑️ Status deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete status: {e}")
            return False
    
    def set_status_privacy(self, privacy_type: str = "my_contacts") -> bool:
        """
        Set status privacy settings.
        
        Args:
            privacy_type: "my_contacts", "only_share", "except"
        """
        try:
            if not self._navigate_to_status():
                return False
            
            # Click privacy button
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
    
    # ── Status Watching (Existing) ────────────────────────────────────────
    
    def start_status_watcher(self, callback: Optional[Callable] = None) -> None:
        """Start background thread to watch for new status updates."""
        if callback:
            self._status_callbacks.append(callback)
            
        if self._status_watcher and self._status_watcher.is_alive():
            logger.warning("Status watcher already running")
            return
            
        self._stop_status_watcher.clear()
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
        """Background loop checking for status updates."""
        seen_statuses = set()
        
        while not self._stop_status_watcher.is_set():
            try:
                status_updates = self.driver.find_elements(By.XPATH, Sel.STATUS_UPDATES)
                
                if status_updates:
                    status_updates[0].click()
                    time.sleep(1)
                    
                    statuses = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
                    
                    for status in statuses:
                        try:
                            name_el = status.find_element(By.XPATH, './/span[@dir="auto"]')
                            contact_name = name_el.text
                            status_id = f"{contact_name}_{datetime.now().date()}"
                            
                            if status_id not in seen_statuses:
                                seen_statuses.add(status_id)
                                
                                status_data = {
                                    'contact': contact_name,
                                    'timestamp': datetime.now(),
                                    'type': 'status'
                                }
                                
                                for callback in self._status_callbacks:
                                    try:
                                        callback(status_data)
                                    except Exception as e:
                                        logger.error(f"Status callback error: {e}")
                                        
                        except Exception as e:
                            continue
                            
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    
                time.sleep(self.config.watch_status_interval)
                
            except Exception as e:
                logger.error(f"Status watcher error: {e}")
                time.sleep(5)
                
    def view_contact_status(self, contact_name: str) -> Optional[str]:
        """View a specific contact's status."""
        try:
            self._find(Sel.STATUS_UPDATES).click()
            time.sleep(1)
            
            statuses = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
            for status in statuses:
                name_el = status.find_element(By.XPATH, './/span[@dir="auto"]')
                if name_el.text == contact_name:
                    status.click()
                    time.sleep(2)
                    
                    status_text = self._exists(Sel.STATUS_TEXT, timeout=2)
                    text = status_text.text if status_text else "(No text)"
                    
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    return text
                    
            logger.warning(f"No status found for {contact_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to view status: {e}")
            return None
    
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
        """Send media file (image, video, document) in best quality."""
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
            logger.info("👉 Open WhatsApp on your phone → Settings → Linked Devices → Link a device")
            logger.info(f"👉 Enter this code: {code}")
            
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
                    
                linked_msg = '//div[contains(text(), "linked")]'
                if self._exists(linked_msg, timeout=1):
                    logger.info("✅ Device linked confirmation received!")
                    return True
            except:
                pass
            time.sleep(2)
            
        logger.warning("Timeout waiting for device linking confirmation")
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
            
    def open_chat(self, contact_name: str) -> None:
        """Open chat by contact name."""
        logger.info(f"Opening chat: {contact_name}")
        
        search = self._find(Sel.SEARCH_BOX)
        search.click()
        search.send_keys(Keys.CONTROL + "a")
        search.send_keys(Keys.DELETE)
        
        self._human_type(search, contact_name, clear_first=False)
        time.sleep(1.2)
        
        row_xpath = Sel.CHAT_ROW_BY_NAME.format(name=contact_name)
        try:
            row = WebDriverWait(self.driver, self.config.element_timeout).until(
                EC.element_to_be_clickable((By.XPATH, row_xpath))
            )
            self._human_mouse_move(row)
            row.click()
            time.sleep(0.8)
            logger.info(f"Chat opened: {contact_name}")
        except TimeoutException:
            search.send_keys(Keys.ESCAPE)
            raise TimeoutException(f"Contact '{contact_name}' not found")


# ── Example Usage & Testing (ELITE v4) ───────────────────────────────────────
if __name__ == "__main__":
    # Configuration
    config = BotConfig(
        firefox_profile_path="/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr",
        enable_human_typing=True,
        broadcast_cooldown=2.0,
        watch_status_interval=30,
    )
    
    with WhatsAppBot(config) as bot:
        
        # ═══════════════════════════════════════════════════════════════
        #  NEW: STATUS POSTING EXAMPLES
        # ═══════════════════════════════════════════════════════════════
        
        # Example 1: Post a simple text status
        # bot.post_text_status("Good morning! ☀️ Have a great day!")
        
        # Example 2: Post a colored text status
        # bot.post_text_status("Feeling blessed! ✨", background_color="#128C7E")
        
        # Example 3: Post a photo status
        # bot.post_photo_status("/path/to/photo.jpg", "Beautiful sunset! 🌅")
        
        # Example 4: Post a video status
        # bot.post_video_status("/path/to/video.mp4", "Check this out! 🎬")
        
        # Example 5: Post a motivational quote status
        # bot.post_motivational_quote()
        
        # Example 6: Post a custom quote
        # bot.post_quote_status("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb", background_color="#075E54")
        
        # Example 7: Set status privacy before posting
        # bot.set_status_privacy("my_contacts")
        # bot.post_text_status("Only my contacts can see this!")
        
        # Example 8: Delete my current status
        # bot.delete_my_status()
        
        # Example 9: Watch for new statuses from contacts
        # def on_new_status(status):
        #     print(f"📢 New status from {status['contact']} at {status['timestamp']}")
        # bot.start_status_watcher(callback=on_new_status)
        # time.sleep(60)
        # bot.stop_status_watcher()
        
        # Example 10: View a contact's status
        # text = bot.view_contact_status("John Doe")
        # if text:
        #     print(f"Status: {text}")
        
        # Example 11: Original functionality still works
        # bot.open_chat("~Taliban Mkristu")
        # bot.send_message("Hello from Elite v4!")
        
        print("✅ WhatsApp Bot v4 (ELITE) is ready!")
        print("\n📱 Status Posting Features Available:")
        print("  - post_text_status(text, background_color, font_size)")
        print("  - post_photo_status(image_path, caption)")
        print("  - post_video_status(video_path, caption)")
        print("  - post_quote_status(quote, author, background_color)")
        print("  - post_motivational_quote()")
        print("  - delete_my_status()")
        print("  - set_status_privacy(privacy_type)")
        print("\n💬 Keep the bot running... (Press Ctrl+C to stop)")
        
        # Keep the bot running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")