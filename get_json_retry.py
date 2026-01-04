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
                    # Optional: notify waiters to re-check sooner
                    self._cond.notify_all()
                    return

                oldest = self._request_timestamps[0]
                wait_time = self.rate_seconds - (now - oldest)
                if wait_time <= 0:
                    continue
                if wait_time > (self.rate_seconds / 2):
                    logger.info("Rate limit reached. Sleeping for %d seconds...", int(wait_time))
                # Efficient wait: releases lock, reacquires on wake/timeout
                self._cond.wait(timeout=wait_time)


"""Ensures we do not exceed MAX_API_REQUESTS per API_REQUESTS_RESET_SEC."""
MAX_API_REQUESTS = 100
API_REQUESTS_RESET_SEC = 120  # seconds
_rate_limiter = RateLimiter(MAX_API_REQUESTS, API_REQUESTS_RESET_SEC)


def get_json_retry(url, max_attempts = 3):
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
                    logger.info("Err 429. Sleeping for %d seconds to reset...", int(API_REQUESTS_RESET_SEC // 2))
                    time.sleep(API_REQUESTS_RESET_SEC // 2)     # wait half the time window for API limit reset
                    continue
            elif e.code == 401:                             # 401: Unauthorized - invalid / expired API key
                # logger.debug(url)                                # debug
                raise
            raise       # raise for error code besides ones listed. ie: HTTP Error 401: Unauthorized - invalid / expired API key
        except urllib.error.URLError as e:  
            if retry < max_attempts-1:      
                logger.warning("URLError: %s", e)
                continue
