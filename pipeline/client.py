"""Thin wrapper around the Tushare Pro API with rate limiting and retries.

Uses the purchased gateway URL (TUSHARE_HTTP_URL) instead of the official
endpoint, per the data vendor's instructions.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

import pandas as pd
import tushare as ts

from .config import Settings, get_settings

log = logging.getLogger(__name__)


class TushareClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.token:
            raise RuntimeError(
                "TUSHARE_TOKEN is not set. Put it in .env at the project root."
            )
        pro = ts.pro_api(self.settings.token)
        # The vendor requires overriding the private attributes on DataApi.
        pro._DataApi__token = self.settings.token
        pro._DataApi__http_url = self.settings.http_url
        self._pro = pro
        self._call_times: deque[float] = deque()
        # Shared by worker threads in bulk ingestion (Module 15); a thread
        # that must wait holds the lock so the per-minute cap stays global.
        self._lock = threading.Lock()

    def _throttle(self) -> None:
        with self._lock:
            now = time.time()
            window = 60.0
            while self._call_times and now - self._call_times[0] > window:
                self._call_times.popleft()
            if len(self._call_times) >= self.settings.max_calls_per_minute:
                sleep_for = window - (now - self._call_times[0]) + 0.1
                log.info("Rate limit reached; sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)
            self._call_times.append(time.time())

    def query(self, api_name: str, **params) -> pd.DataFrame:
        """Call a Tushare API with throttling and retry. Returns the raw frame."""
        last_err: Exception | None = None
        for attempt in range(1, self.settings.retry_attempts + 1):
            self._throttle()
            try:
                df = self._pro.query(api_name, **params)
                if df is None:
                    df = pd.DataFrame()
                return df
            except Exception as e:  # network errors, rate-limit messages, etc.
                last_err = e
                log.warning(
                    "%s attempt %d/%d failed: %s",
                    api_name, attempt, self.settings.retry_attempts, e,
                )
                time.sleep(self.settings.retry_backoff_seconds * attempt)
        raise RuntimeError(f"Tushare API {api_name} failed after retries: {last_err}")
