"""
Thin httpx wrapper for the Instagram Graph API.

Handles:
  - Base URL construction (includes API version).
  - Access-token injection on every request.
  - Automatic retries with exponential back-off for transient errors.
  - Centralised error raising so callers get clean exceptions.
"""

import httpx
from config.settings import get_settings


# Retry-eligible HTTP status codes (transient server / rate-limit errors).
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Default timeout for every request (seconds).
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

# Retry configuration.
_MAX_RETRIES = 3
_BACKOFF_FACTOR = 1.0   # 1s, 2s, 4s


class GraphAPIError(Exception):
    """Raised when the Graph API returns a non-2xx response."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        error = body.get("error", {})
        message = error.get("message", str(body))
        super().__init__(f"Graph API {status_code}: {message}")


class GraphClient:
    """
    Reusable, synchronous HTTP client for the Facebook/Instagram Graph API.

    Usage::

        client = GraphClient()
        data = client.get("/<IG_ID>", params={"fields": "followers_count"})
    """

    def __init__(self):
        settings = get_settings().instagram
        self._base_url = settings.api_base          # e.g. https://graph.facebook.com/v25.0
        self._access_token = settings.access_token
        self._client = httpx.Client(timeout=_TIMEOUT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> dict:
        """
        Send a GET request to *path* (appended to the versioned base URL).

        Parameters
        ----------
        path : str
            Graph API path, e.g. ``"/<IG_ID>/insights"`` or ``"/<MEDIA_ID>"``.
            A leading ``/`` is added automatically if missing.
        params : dict, optional
            Query-string parameters (``fields``, ``metric``, ``period``, …).

        Returns
        -------
        dict
            The full parsed JSON response body.

        Raises
        ------
        GraphAPIError
            On any non-2xx response after retries are exhausted.
        """
        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{self._base_url}{path}"

        merged_params = {"access_token": self._access_token}
        if params:
            merged_params.update(params)

        return self._request_with_retry("GET", url, merged_params)

    def close(self):
        """Close the underlying httpx client."""
        self._client.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _request_with_retry(self, method: str, url: str, params: dict) -> dict:
        """Execute request with exponential back-off on retryable errors."""
        import time

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.request(method, url, params=params)

                if response.status_code == 200:
                    return response.json()

                # Retryable? sleep & retry.
                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_FACTOR * (2 ** attempt))
                    continue

                # Non-retryable or final attempt → raise.
                raise GraphAPIError(response.status_code, response.json())

            except httpx.TransportError as exc:
                # Network-level errors (DNS, connection reset, …).
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_FACTOR * (2 ** attempt))
                    continue
                raise

        # Should not reach here, but just in case.
        raise last_exc  # type: ignore[misc]

    # Context-manager support so callers can do `with GraphClient() as c:`
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
