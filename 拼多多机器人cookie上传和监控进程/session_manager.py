import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_session = None

def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=200)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        _session.timeout = 15  # Default timeout
    return _session