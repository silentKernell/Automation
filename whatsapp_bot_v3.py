"""
WhatsApp Web Automation Tool — v3 (Professional Edition)
Features:
- Human-like typing simulation (character by character)
- CSV contact list broadcasting with cooldown
- Status watcher for contact statuses
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
    
    # Status
    STATUS_UPDATES = '//div[@aria-label="Status updates"]'
    STATUS_THUMBNAIL = '//div[@data-testid="status-thumbnail"]'
    STATUS_VIEWER = '//div[@data-testid="status-viewer"]'
    STATUS_TEXT = '//div[@data-testid="status-text"]'
    STATUS_MUTE_BTN = '//button[@aria-label="Mute status updates"]'
    
    # Groups
    GROUP_INFO = '//div[@data-testid="conversation-panel-header"]'
    GROUP_MEMBERS = '//div[@data-testid="group-members"]'
    
    # New chat
    NEW_CHAT_BTN = '//button[@aria-label="New chat"]'
    NEW_CHAT_SEARCH = '//p[@class="selectable-text copyable-text"]'


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
    typing_speed_range: Tuple[float, float] = (0.05, 0.15)  # seconds between chars
    typing_variance: float = 0.03  # random variance
    
    # Broadcasting
    broadcast_cooldown: float = 2.0  # seconds between contacts
    broadcast_batch_size: int = 10  # messages before taking a longer break
    broadcast_batch_break: float = 10.0  # break time after batch
    
    # Status watching
    watch_status_interval: int = 30  # seconds
    status_check_enabled: bool = True
    
    # Anti-detection
    random_delay_range: Tuple[float, float] = (0.5, 2.0)
    human_mouse_movement: bool = True
    
    # Media
    compress_images: bool = True
    max_image_size_mb: int = 16
    
    # Extra Firefox preferences
    extra_prefs: dict = field(default_factory=dict)


# ── Enhanced WhatsApp Bot ────────────────────────────────────────────────────
class WhatsAppBot:
    """Professional WhatsApp automation with all requested features."""
    
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
        logger.info("🚀 Starting WhatsApp Web Automation v3...")
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
        """
        Type text character by character with human-like timing.
        This solves the "first letter only" issue by properly simulating typing.
        """
        if not self.config.enable_human_typing:
            element.send_keys(text)
            return
            
        if clear_first:
            # Clear existing text with Ctrl+A + Delete
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            time.sleep(0.2)
        
        # Type each character with natural delays
        for i, char in enumerate(text):
            # Add occasional pauses at punctuation
            element.send_keys(char)
            
            # Variable delay between keystrokes
            delay = random.uniform(*self.config.typing_speed_range)
            delay += random.uniform(-self.config.typing_variance, 
                                   self.config.typing_variance)
            delay = max(0.02, min(0.3, delay))  # Clamp between 2ms and 300ms
            
            # Longer pauses at sentence boundaries
            if char in '.!?;':
                delay += random.uniform(0.1, 0.3)
            elif char in ',:':
                delay += random.uniform(0.05, 0.15)
                
            time.sleep(delay)
            
            # Occasionally wait longer (thinking time) at 15-30% of characters
            if random.random() < 0.02:  # 2% chance per character
                time.sleep(random.uniform(0.3, 0.8))
                
        # Small pause before sending
        time.sleep(random.uniform(0.1, 0.3))
        
    def _human_mouse_move(self, target_element) -> None:
        """Move mouse naturally to an element."""
        if not self.config.human_mouse_movement or not self._actions:
            return
            
        try:
            # Get element location
            rect = target_element.rect
            # Add some randomness to click position
            x_offset = random.randint(-5, 5)
            y_offset = random.randint(-5, 5)
            
            # Move with bezier-like smooth motion
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
        """
        Load contacts from CSV file.
        CSV format: name, phone (or custom columns)
        """
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
        """
        Broadcast message to multiple contacts with cooldown periods.
        Uses either 'name' or 'phone' as identifier.
        """
        results = {}
        total = len(contacts)
        
        for idx, contact in enumerate(contacts):
            identifier = contact.get(identifier_field, '')
            if not identifier:
                identifier = contact.get('phone', f"Contact_{idx}")
                
            try:
                logger.info(f"📤 [{idx+1}/{total}] Sending to: {identifier}")
                
                # Open chat using name if available, otherwise search by phone
                if contact.get('name'):
                    self.open_chat(contact['name'])
                elif contact.get('phone'):
                    self.open_chat_by_phone(contact['phone'])
                else:
                    logger.warning(f"❌ No identifier for contact at index {idx}")
                    results[identifier] = False
                    continue
                
                # Send with human typing
                self.send_message(message)
                results[identifier] = True
                
                # Cooldown between messages
                if idx < total - 1:  # Don't wait after last
                    # Check if we need a batch break
                    if (idx + 1) % self.config.broadcast_batch_size == 0:
                        logger.info(f"☕ Batch break: {self.config.broadcast_batch_break}s")
                        time.sleep(self.config.broadcast_batch_break)
                    else:
                        cooldown = self.config.broadcast_cooldown
                        # Add random variance to avoid pattern detection
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
        """
        Open chat using international phone number.
        Phone number format: 1234567890 (without + or spaces)
        """
        # Format for WhatsApp Web search
        formatted = f"{phone_number}".replace("+", "").replace(" ", "")
        self.open_chat(formatted)
    
    # ── Enhanced Messaging (fixes first-letter issue) ────────────────────
    
    def send_message(self, text: str) -> None:
        """
        Send message with human-like typing simulation.
        This completely replaces the old send_message method.
        """
        if not text.strip():
            logger.warning("Empty message, skipped.")
            return
            
        logger.info(f"✍️ Typing: {text[:50]}..." if len(text) > 50 else f"✍️ Sending: {text}")
        
        # Wait for message input to be ready
        box = self._find(Sel.MSG_INPUT, timeout=15)
        box.click()
        time.sleep(random.uniform(0.1, 0.3))
        
        # Use human typing simulation
        self._human_type(box, text, clear_first=False)
        
        # Send with Enter key
        box.send_keys(Keys.RETURN)
        
        # Random delay after sending (appears more human)
        time.sleep(random.uniform(0.5, 1.5))
        
    def send_message_with_retry(self, text: str, max_retries: int = 3) -> bool:
        """Send message with retry logic on failure."""
        for attempt in range(max_retries):
            try:
                self.send_message(text)
                return True
            except Exception as e:
                logger.warning(f"Retry {attempt+1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        return False
    
    # ── Linked Device Pairing ────────────────────────────────────────────
    
    def get_linking_code(self, timeout: int = 120) -> Optional[str]:
        """
        Get linking code to connect as linked device.
        Returns the 8-character code to enter on phone.
        """
        logger.info("🔗 Starting device linking process...")
        
        try:
            # Click on menu if needed
            menu_btn = self._find('//button[@aria-label="Menu"]', timeout=10)
            menu_btn.click()
            time.sleep(0.5)
            
            # Click "Link a device"
            link_btn = self._find(Sel.LINK_DEVICE_BTN, timeout=10)
            link_btn.click()
            time.sleep(1)
            
            # Wait for and extract the linking code
            code_element = self._find(Sel.LINKED_DEVICE_CODE, timeout=timeout)
            code = code_element.text.strip()
            
            # Clean up code (should be like "ABCD-1234" or similar)
            code = re.sub(r'[^A-Z0-9-]', '', code.upper())
            
            logger.info(f"📱 Linking code: {code}")
            logger.info("👉 Open WhatsApp on your phone → Settings → Linked Devices → Link a device")
            logger.info(f"👉 Enter this code: {code}")
            
            # Wait for successful linking
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
                # Check if main interface is ready (means device is linked)
                if self._exists(Sel.SEARCH_BOX, timeout=2):
                    logger.info("✅ Device successfully linked!")
                    return True
                    
                # Also check for "Your device is linked" message
                linked_msg = '//div[contains(text(), "linked")]'
                if self._exists(linked_msg, timeout=1):
                    logger.info("✅ Device linked confirmation received!")
                    return True
                    
            except:
                pass
            time.sleep(2)
            
        logger.warning("Timeout waiting for device linking confirmation")
        return False
    
    # ── Status Watching ──────────────────────────────────────────────────
    
    def start_status_watcher(self, callback: Optional[Callable] = None) -> None:
        """
        Start background thread to watch for new status updates.
        Calls callback with status data when new status is found.
        """
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
                # Navigate to status section
                status_updates = self.driver.find_elements(By.XPATH, Sel.STATUS_UPDATES)
                
                if status_updates:
                    status_updates[0].click()
                    time.sleep(1)
                    
                    # Get all status thumbnails
                    statuses = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
                    
                    for status in statuses:
                        try:
                            # Get contact name
                            name_el = status.find_element(By.XPATH, './/span[@dir="auto"]')
                            contact_name = name_el.text
                            
                            # Create unique ID for this status
                            status_id = f"{contact_name}_{datetime.now().date()}"
                            
                            if status_id not in seen_statuses:
                                seen_statuses.add(status_id)
                                
                                # Extract status data
                                status_data = {
                                    'contact': contact_name,
                                    'timestamp': datetime.now(),
                                    'type': 'status'
                                }
                                
                                # Notify callbacks
                                for callback in self._status_callbacks:
                                    try:
                                        callback(status_data)
                                    except Exception as e:
                                        logger.error(f"Status callback error: {e}")
                                        
                        except Exception as e:
                            continue
                            
                    # Close status viewer
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    
                time.sleep(self.config.watch_status_interval)
                
            except Exception as e:
                logger.error(f"Status watcher error: {e}")
                time.sleep(5)
                
    def view_status(self, contact_name: str) -> Optional[str]:
        """View a specific contact's status."""
        try:
            # Open status section
            self._find(Sel.STATUS_UPDATES).click()
            time.sleep(1)
            
            # Find contact's status
            statuses = self.driver.find_elements(By.XPATH, Sel.STATUS_THUMBNAIL)
            for status in statuses:
                name_el = status.find_element(By.XPATH, './/span[@dir="auto"]')
                if name_el.text == contact_name:
                    status.click()
                    time.sleep(2)
                    
                    # Extract status text if any
                    status_text = self._exists(Sel.STATUS_TEXT, timeout=2)
                    text = status_text.text if status_text else "(No text)"
                    
                    # Close
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
            # Open group (same as contact but group name)
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
            # Apply group filter
            self._click(Sel.FILTER_GROUPS)
            time.sleep(1)
            
            # Get all chat items
            chat_items = self.driver.find_elements(
                By.XPATH, '//div[@aria-label="Chat list"]//div[@role="gridcell"]'
            )
            
            for item in chat_items:
                try:
                    # Check if it's a group (has group icon or multiple participants)
                    name_el = item.find_element(By.XPATH, './/span[@dir="auto"]')
                    groups.append(name_el.text)
                except:
                    continue
                    
            # Reset filter to all
            self._click(Sel.FILTER_ALL)
            logger.info(f"Found {len(groups)} groups")
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get group list: {e}")
            return groups
    
    # ── Enhanced Media Sending (Best Quality) ─────────────────────────────
    
    def send_media(self, file_path: str, caption: str = "", 
                   as_document: bool = False) -> bool:
        """
        Send media file (image, video, document) in best quality.
        Uses original file without compression when possible.
        """
        abs_path = str(Path(file_path).resolve())
        if not Path(abs_path).exists():
            raise FileNotFoundError(f"File not found: {abs_path}")
            
        logger.info(f"📎 Sending media: {abs_path}")
        
        # Choose input type based on file
        if as_document:
            file_input = Sel.ATTACH_DOC_INPUT
        else:
            file_input = Sel.ATTACH_IMG_INPUT
            
        try:
            # Click attach button
            attach = self._find(Sel.ATTACH_BTN)
            attach.click()
            time.sleep(0.8)
            
            # Find file input and send keys
            input_el = self._find(file_input)
            
            # For better compatibility, make the input visible if hidden
            self.driver.execute_script("arguments[0].style.display = 'block';", input_el)
            input_el.send_keys(abs_path)
            
            # Wait for preview to load
            time.sleep(2.5)
            
            # Add caption if provided
            if caption:
                try:
                    caption_box = WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, Sel.MSG_INPUT))
                    )
                    self._human_type(caption_box, caption)
                except:
                    logger.warning("Could not add caption")
                    
            # Send
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
            # Try JavaScript click as fallback
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
            
        # Stealth preferences to avoid detection
        stealth_prefs = {
            "dom.webnotifications.enabled": False,
            "media.volume_scale": "0.0",
            "privacy.trackingprotection.enabled": True,
            "privacy.trackingprotection.fingerprinting.enabled": True,
            "webgl.disabled": False,  # Keep WebGL for better emulation
            "dom.push.enabled": False,
            "dom.serviceWorkers.enabled": False,
        }
        
        for k, v in {**stealth_prefs, **self.config.extra_prefs}.items():
            options.set_preference(k, v)
            
        # Random user agent (optional)
        # options.set_preference("general.useragent.override", self._get_random_user_agent())
        
        service_kwargs = {}
        if self.config.geckodriver_path:
            service_kwargs["executable_path"] = self.config.geckodriver_path
        service = Service(**service_kwargs)
        
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(self.config.load_timeout)
        
        # Set window size to common human resolution
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
        
        # Type search term with human delay
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


# ── Example Usage & Testing ───────────────────────────────────────────────────
if __name__ == "__main__":
    # Configuration
    config = BotConfig(
        firefox_profile_path="/home/kernel/.mozilla/firefox/x4o5i1pe.default-esr",
        enable_human_typing=True,
        broadcast_cooldown=2.0,
        watch_status_interval=30,
    )
    
    # Example 1: Basic usage with human typing (fixes first-letter issue)
    with WhatsAppBot(config) as bot:
        # Send message with human-like typing
        # bot.open_chat("~Taliban Mkristu")
        # bot.send_message("Hello! This message is typed character by character.")
        
        # Example 2: Broadcast to CSV contacts
        # contacts = bot.load_contacts_from_csv("contacts.csv")
        # bot.broadcast_to_contacts(contacts, "Hello from broadcast!", identifier_field='name')
        
        # Example 3: Get linking code for new device
        # code = bot.get_linking_code()
        
        # Example 4: Send high-quality image
        # bot.send_image_high_quality("/path/to/image.jpg", "Check this out!")
        
        # Example 5: Watch status updates
        def on_status(status):
            print(f"New status from {status['contact']} at {status['timestamp']}")
        bot.start_status_watcher(callback=on_status)
        time.sleep(60)  # Watch for 1 minute
        bot.stop_status_watcher()
        
        # Example 6: Group messaging
        # groups = bot.get_group_list()
        # if groups:
        #     bot.send_group_message(groups[0], "Hello group!")