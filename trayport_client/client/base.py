"""Base HTTP client for Trayport API with rate limiting and retry logic."""

import asyncio
from typing import Any, Dict, Optional

import httpx
import structlog
from httpx import HTTPStatusError, RequestError

from ..config.constants import (
    ANALYTICS_BASE_URL,
    API_KEY_HEADER,
    DEFAULT_REQUEST_TIMEOUT,
    REFERENCE_BASE_URL,
    RETRYABLE_STATUS_CODES,
    USER_AGENT,
)
from ..exceptions.api import (
    TrayportAPIError,
    TrayportAuthenticationError,
    TrayportNotFoundError,
    TrayportRateLimitError,
    TrayportServerError,
)
from ..exceptions.client import TrayportConnectionError, TrayportTimeoutError
from .auth import TrayportAuth
from .rate_limiter import DualTierRateLimiter, Priority

logger = structlog.get_logger(__name__)


class BaseClient:
    """Base HTTP client with rate limiting and retry logic."""
    
    def __init__(
        self,
        api_key: str,
        rate_limiter: Optional[DualTierRateLimiter] = None,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = 3,
    ):
        """
        Initialize base HTTP client.
        
        Args:
            api_key: Trayport API key
            rate_limiter: Rate limiter instance (creates default if None)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for retryable errors
        """
        self.api_key = api_key
        self.rate_limiter = rate_limiter or DualTierRateLimiter()
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Create auth handler
        self.auth = TrayportAuth(api_key)
        
        # Create HTTP client with optimal settings
        self.session = httpx.AsyncClient(
            auth=self.auth,
            http2=True,  # Enable HTTP/2
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Encoding": "br, gzip, deflate",  # Brotli preferred
            },
        )
        
        logger.info(
            "Base client initialized",
            timeout=timeout,
            max_retries=max_retries,
        )
    
    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.NORMAL,
    ) -> Any:
        """
        Make HTTP request with rate limiting and retry logic.
        
        Args:
            method: HTTP method
            url: Full URL or path (will prepend base URL if path)
            params: Query parameters
            json: JSON body
            priority: Request priority for rate limiter
            
        Returns:
            Parsed JSON response
            
        Raises:
            TrayportAPIError: For API errors
            TrayportConnectionError: For connection issues
            TrayportTimeoutError: For timeout errors
        """
        # Ensure full URL
        if not url.startswith("http"):
            # Determine base URL from path
            if "/instruments" in url or "/markets" in url or "/sequences" in url:
                url = REFERENCE_BASE_URL + url
            else:
                url = ANALYTICS_BASE_URL + url
        
        # Attempt request with retries
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Wait for rate limit
                await self.rate_limiter.acquire(priority)
                
                # Make request
                logger.debug(
                    "Making request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                )
                
                response = await self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )
                
                # Report success to rate limiter
                self.rate_limiter.report_success()
                
                # Check for errors
                if response.status_code >= 400:
                    logger.debug(
                        f"Error response",
                        status=response.status_code,
                        url=url,
                        response_text=response.text[:500]
                    )
                    self._handle_error_response(response)
                
                # Return parsed JSON
                return response.json()
                
            except httpx.TimeoutException as e:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                last_error = TrayportTimeoutError(f"Request timed out: {str(e)}")
                
            except httpx.RequestError as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {str(e)}")
                last_error = TrayportConnectionError(f"Connection error: {str(e)}")
                
            except TrayportRateLimitError as e:
                # Report to rate limiter and retry
                self.rate_limiter.report_429()
                logger.warning(f"Rate limit hit on attempt {attempt + 1}")
                last_error = e
                
            except TrayportServerError as e:
                # Retry on server errors
                logger.warning(f"Server error on attempt {attempt + 1}: {str(e)}")
                last_error = e
                
            except TrayportAPIError as e:
                # Don't retry on client errors (4xx except 429)
                logger.error(f"API error: {str(e)}")
                raise
            
            # Check if we should retry
            if last_error and isinstance(last_error, (TrayportRateLimitError, TrayportServerError, TrayportTimeoutError, TrayportConnectionError)):
                attempt += 1
                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + (asyncio.create_task(asyncio.sleep(0)).done() and 0.1)
                    logger.info(f"Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
            else:
                break
        
        # Exhausted retries
        if last_error:
            logger.error(f"All retry attempts failed")
            raise last_error
        
        raise TrayportAPIError("Request failed with unknown error")
    
    def _handle_error_response(self, response: httpx.Response) -> None:
        """
        Handle error responses and raise appropriate exceptions.
        
        Args:
            response: HTTP response
            
        Raises:
            TrayportAPIError: Appropriate error based on status code
        """
        status_code = response.status_code
        
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except:
            message = response.text
        
        if status_code == 401:
            raise TrayportAuthenticationError(message)
        elif status_code == 404:
            raise TrayportNotFoundError(message)
        elif status_code == 429:
            raise TrayportRateLimitError(message)
        elif status_code >= 500:
            raise TrayportServerError(f"Server error {status_code}: {message}")
        else:
            raise TrayportAPIError(f"API error {status_code}: {message}")
    
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Convenience method for GET requests."""
        return await self.request("GET", url, params=params, **kwargs)
    
    async def post(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Convenience method for POST requests."""
        return await self.request("POST", url, json=json, **kwargs)
    
    async def close(self) -> None:
        """Close HTTP session and cleanup."""
        await self.session.aclose()
        await self.rate_limiter.shutdown()
        logger.info("Base client closed")