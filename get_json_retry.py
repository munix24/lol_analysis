import urllib.request
import urllib.parse
import urllib.error
import time
import json
from collections import deque
import logging
import threading

logger = logging.getLogger(__name__)

class RateLimiter:
    """Thread-safe rolling-window rate limiter using a Condition.

    Allows up to `max_requests` within any `rate_seconds` rolling window.
    """
    def __init__(self, max_requests: int, rate_seconds: float):
        self.max_requests = int(max_requests)
        self.rate_seconds = float(rate_seconds)
        self._request_timestamps = deque()
        self._cond = threading.Condition()
        self._request_meter = RequestMeter(60 * 60)

    def wait_for_slot(self):
        """Block until a slot is available, then record the request timestamp."""
        with self._cond:
            while True:
                now = time.time()
                # Cleanup expired timestamps
                while self._request_timestamps and now - self._request_timestamps[0] > self.rate_seconds:
                    self._request_timestamps.popleft()

                if len(self._request_timestamps) < self.max_requests:
                    self._request_timestamps.append(now)
                    self._request_meter.record(now)
                    # Optional: notify waiters to re-check sooner
                    self._cond.notify_all()
                    return

                oldest = self._request_timestamps[0]
                wait_time = self.rate_seconds - (now - oldest)
                if wait_time <= 0:
                    continue

                if wait_time > (self.rate_seconds / 3):     # log if waiting significant time
                    logger.info("API rate limit reached. Sleeping for %d seconds...", int(wait_time))
                    # include a summary of requests (total and last-hour) for observability.
                    logger.info(
                        "APIs called: total=%d, last_hour=%d, seconds_since_first=%.0f, reqs_per_hour=%.0f",
                        self._request_meter.total,
                        self._request_meter.count,
                        self._request_meter.seconds_since_first,
                        self._request_meter.reqs_per_hour,
                    )
                # Efficient wait: releases lock, reacquires on wake/timeout
                self._cond.wait(timeout=wait_time)

class RequestMeter:
    """Counts requests within a rolling longer window (e.g. 1 hour).

    Keeps a deque of timestamps for the rolling window and a simple
    cumulative counter. Thread-safe via an internal Lock.
    """
    def __init__(self, window_seconds: float = 3600.0):
        self.window_seconds = float(window_seconds)
        self._timestamps = deque()
        self._lock = threading.Lock()
        self._total = 0
        # Record the start time for this meter. seconds_since_first will
        # report seconds since this time (i.e. how long the meter has been
        # active), rather than the age of the oldest timestamp in the deque.
        self._started_at = time.time()

    def record(self, ts: float = None):
        ts = ts or time.time()
        with self._lock:
            self._timestamps.append(ts)
            self._total += 1
            cutoff = ts - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

    @property
    def count(self) -> int:
        """Number of requests in the current rolling window (uses now())."""
        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return len(self._timestamps)

    @property
    def total(self) -> int:
        """Cumulative total of recorded requests."""
        with self._lock:
            return int(self._total)

    @property
    def seconds_since_first(self) -> float:
        """Return seconds since this `RequestMeter` was created."""
        now = time.time()
        seconds = now - float(self._started_at)
        return float(seconds) if seconds >= 0.0 else 0.0

    @property
    def reqs_per_hour(self) -> float:
        """Estimate average requests per hour since the meter was created."""
        total = self.total
        seconds = self.seconds_since_first
        if total <= 0:
            return 0.0
        if seconds <= 0.0:
            return float(total)
        return float(total) * 3600.0 / float(seconds)

    def log_request_stats(self):
        """Log an info summary with total requests and requests in the last hour."""
        try:
            now = time.time()
            logger.info(
                "Requests summary: total=%d, last_hour=%d, seconds_since_first=%.0f, reqs_per_hour=%.0f",
                self.total,
                self.count,
                self.seconds_since_first,
                self.reqs_per_hour,
            )
        except Exception:
            logger.exception("Failed to compute request stats")

"""Ensures we do not exceed MAX_API_REQUESTS per API_REQUESTS_RESET_SEC."""
MAX_API_REQUESTS = 100
API_REQUESTS_RESET_SEC = 120  # seconds
_rate_limiter = RateLimiter(MAX_API_REQUESTS, API_REQUESTS_RESET_SEC)

def get_json_retry(url, max_attempts = 10):
    for retry in range(max_attempts):
        try:
            logger.debug("%s", url)
            logger.debug("%d", len(_rate_limiter._request_timestamps))
            _rate_limiter.wait_for_slot()  # enforce rate limit before request
            response = urllib.request.urlopen(url)
            response_json = json.loads(response.read())
            return response_json                            # successful
        except urllib.error.HTTPError as e:    
            logger.warning("HTTPError: %s", e)
            if e.code == 502 or e.code == 403:              # only retry on 502 Bad Gateway / 403 Forbidden (random 20/s api rate limit?)
                if retry < max_attempts-1:  
                    continue
            elif e.code == 404:                             # 404: Not Found
                if retry < max_attempts-1:  
                    time.sleep(15)                          # wait until game starts
                    continue
            elif e.code == 429:                             # HTTP Error 429: Too Many Requests (api rate limit)
                if retry < max_attempts-1:
                    # Prefer honoring server-provided Retry-After header when present.
                    retry_after = None
                    try:
                        # HTTPError behaves like a response; headers may be in .headers
                        if hasattr(e, 'headers') and e.headers is not None:
                            retry_after = e.headers.get('Retry-After')
                        else:
                            # fallback to info()/getheader if available
                            try:
                                retry_after = e.getheader('Retry-After')
                            except Exception:
                                retry_after = None
                    except Exception:
                        retry_after = None

                    if retry_after:
                        try:
                            # Retry-After can be seconds or HTTP-date; try numeric first
                            sleep_time = int(float(retry_after))
                        except Exception:
                            # Could be an HTTP-date or unparseable; fall back to heuristic
                            sleep_time = int(API_REQUESTS_RESET_SEC // 8)
                    else:
                        sleep_time = int(API_REQUESTS_RESET_SEC // 8)

                    logger.info("Err 429. Sleeping for %d seconds to reset... (Retry-After=%s)", sleep_time, str(retry_after))
                    time.sleep(sleep_time)
                    continue
            elif e.code == 401:                             # 401: Unauthorized - invalid / expired API key
                raise

            # raise       # raise for error code besides ones listed. ie: HTTP Error 401: Unauthorized - invalid / expired API key
        except urllib.error.URLError as e:  
            if retry < max_attempts-1:      
                logger.warning("URLError: %s", e)
                continue
    
def get_api_request_total() -> int:
    """Return the cumulative total number of API requests recorded by the internal meter."""
    try:
        return int(_rate_limiter._request_meter.total)
    except Exception:
        return 0

def get_api_requests_last_hour() -> int:
    """Return the number of requests seen in the last rolling hour window."""
    try:
        return int(_rate_limiter._request_meter.count)
    except Exception:
        return 0

def get_api_reqs_per_hour() -> float:
    """Return the average requests per hour since the meter was created."""
    try:
        return float(_rate_limiter._request_meter.reqs_per_hour)
    except Exception:
        return 0.0

def get_request_stats():
    """Return a dict with request statistics: total, last_hour, seconds_since_first, reqs_per_hour."""
    try:
        rm = _rate_limiter._request_meter
        return {
            'total': int(rm.total),
            'last_hour': int(rm.count),
            'seconds_since_first': float(rm.seconds_since_first),
            'reqs_per_hour': float(rm.reqs_per_hour),
        }
    except Exception:
        return {'total': 0, 'last_hour': 0, 'seconds_since_first': 0.0, 'reqs_per_hour': 0.0}
