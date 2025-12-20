from urllib.request import urlopen
import urllib.parse
import time
import json
from collections import deque

# Global deque to track request timestamps
_request_timestamps = deque()
MAX_API_REQUESTS = 100
API_REQ_RESET_SECs = 120  # seconds

def _wait_for_rate_limit():
    """Ensures we do not exceed MAX_API_REQUESTS per API_REQ_RESET_SECs."""
    now = time.time()
    # Remove timestamps older than API_REQ_RESET_SECs
    while _request_timestamps and now - _request_timestamps[0] > API_REQ_RESET_SECs:
        _request_timestamps.popleft()
    if len(_request_timestamps) >= MAX_API_REQUESTS:
        # Wait until the oldest request leaves the window
        wait_time = API_REQ_RESET_SECs - (now - _request_timestamps[0])
        if wait_time > (API_REQ_RESET_SECs / 2):                            # only print if waiting significant time to not flood output
            print(f"Rate limit reached. Sleeping for {int(wait_time)} seconds...")
        time.sleep(wait_time)
        _wait_for_rate_limit()  # recursive check after sleep
    # Record the new request timestamp
    _request_timestamps.append(time.time())

def get_json_retry(url, max_attempts = 3):
    for retry in range(max_attempts):
        _wait_for_rate_limit()  # enforce rate limit before request
        try:
            response=urllib.request.urlopen(url)
            response_json = json.loads(response.read())
            return response_json                            # successful
        except urllib.error.HTTPError as e:    
            print(e)
            if e.code == 502 or e.code == 403:              # only retry on 502 Bad Gateway / 403 Forbidden (random 20/s api rate limit?)
                if retry < max_attempts-1:  
                    continue
            elif e.code == 404:                             # 404: Not Found
                if retry < max_attempts-1:  
                    time.sleep(15)                          # wait until game starts
                    continue
            elif e.code == 429:                             # HTTP Error 429: Too Many Requests (api rate limit)
                if retry < max_attempts-1:  
                    print(f"Err 429. Sleeping for {int(API_REQ_RESET_SECs // 2)} seconds to reset...")
                    time.sleep(API_REQ_RESET_SECs // 2)     # wait half the time window for API limit reset
                    continue
            elif e.code == 401:                             # 401: Unauthorized - invalid / expired API key
                # print(url)                                # debug
                raise
            raise       # raise for error code besides ones listed. ie: HTTP Error 401: Unauthorized - invalid / expired API key
        except urllib.error.URLError as e:  
            if retry < max_attempts-1:      
                print(e)
                continue
