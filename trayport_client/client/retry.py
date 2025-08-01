"""Retry logic with exponential backoff and jitter."""

import asyncio
import random
from dataclasses import dataclass
from typing import Callable, Optional, Set, Type, Union

import httpx
import structlog

from ..config.constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_RETRY_JITTER,
    DEFAULT_RETRY_MAX_WAIT,
    RETRYABLE_STATUS_CODES,
)
from ..exceptions.api import TrayportAPIError, TrayportError

logger = structlog.get_logger(__name__)


@dataclass
class RetryStrategy:
    """Configuration for retry behavior."""
    
    max_attempts: int = DEFAULT_MAX_RETRIES
    backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR
    max_delay: float = DEFAULT_RETRY_MAX_WAIT
    jitter_factor: float = DEFAULT_RETRY_JITTER
    retryable_statuses: Set[int] = None
    retryable_exceptions: Set[Type[Exception]] = None
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.retryable_statuses is None:
            self.retryable_statuses = RETRYABLE_STATUS_CODES.copy()
        
        if self.retryable_exceptions is None:
            self.retryable_exceptions = {
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.PoolTimeout,
            }
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds with jitter applied
        """
        # Exponential backoff: 2^attempt * backoff_factor
        base_delay = min(
            self.backoff_factor * (2 ** attempt),
            self.max_delay
        )
        
        # Add jitter to prevent thundering herd
        jitter = base_delay * self.jitter_factor * random.random()
        
        return base_delay + jitter
    
    def should_retry(
        self,
        exception: Optional[Exception] = None,
        status_code: Optional[int] = None,
        attempt: int = 0,
    ) -> bool:
        """
        Determine if request should be retried.
        
        Args:
            exception: Exception that occurred
            status_code: HTTP status code
            attempt: Current attempt number
            
        Returns:
            True if request should be retried
        """
        if attempt >= self.max_attempts:
            return False
        
        # Check exception type
        if exception:
            if isinstance(exception, TrayportAPIError):
                return exception.is_retryable
            
            for exc_type in self.retryable_exceptions:
                if isinstance(exception, exc_type):
                    return True
        
        # Check status code
        if status_code and status_code in self.retryable_statuses:
            return True
        
        return False


class RetryHandler:
    """Handles retry logic for HTTP requests."""
    
    def __init__(
        self,
        strategy: Optional[RetryStrategy] = None,
        on_retry: Optional[Callable] = None,
    ) -> None:
        """
        Initialize retry handler.
        
        Args:
            strategy: Retry strategy configuration
            on_retry: Callback function called before each retry
        """
        self.strategy = strategy or RetryStrategy()
        self.on_retry = on_retry
        
        # Metrics
        self.total_retries = 0
        self.successful_retries = 0
        self.failed_retries = 0
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> any:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from successful function execution
            
        Raises:
            Last exception if all retries fail
        """
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.strategy.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                
                # If this was a retry, count it as successful
                if attempt > 0:
                    self.successful_retries += 1
                    logger.info(
                        "Retry successful",
                        attempt=attempt,
                        total_attempts=self.strategy.max_attempts + 1,
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                status_code = None
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                elif isinstance(e, TrayportAPIError):
                    status_code = e.status_code
                
                if not self.strategy.should_retry(
                    exception=e,
                    status_code=status_code,
                    attempt=attempt,
                ):
                    logger.debug(
                        "Not retrying request",
                        attempt=attempt,
                        exception=str(e),
                        status_code=status_code,
                    )
                    raise
                
                # This is the last attempt
                if attempt == self.strategy.max_attempts:
                    self.failed_retries += 1
                    logger.error(
                        "All retry attempts failed",
                        attempts=attempt + 1,
                        last_error=str(e),
                    )
                    raise
                
                # Calculate delay
                delay = self.strategy.calculate_delay(attempt)
                
                # Log retry attempt
                self.total_retries += 1
                logger.warning(
                    "Retrying request",
                    attempt=attempt + 1,
                    max_attempts=self.strategy.max_attempts + 1,
                    delay=f"{delay:.2f}s",
                    error=str(e),
                    status_code=status_code,
                )
                
                # Call retry callback if provided
                if self.on_retry:
                    try:
                        await self.on_retry(
                            attempt=attempt,
                            delay=delay,
                            exception=e,
                        )
                    except Exception as callback_error:
                        logger.error(
                            "Error in retry callback",
                            error=str(callback_error),
                        )
                
                # Wait before retrying
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Retry logic error: no exception to raise")
    
    def get_metrics(self) -> dict:
        """Get retry handler metrics."""
        return {
            "total_retries": self.total_retries,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "success_rate": (
                self.successful_retries / self.total_retries
                if self.total_retries > 0
                else 0.0
            ),
        }
    
    def reset_metrics(self) -> None:
        """Reset retry metrics."""
        self.total_retries = 0
        self.successful_retries = 0
        self.failed_retries = 0


class RetryAfterHandler:
    """Handles Retry-After headers from 429 responses."""
    
    @staticmethod
    def parse_retry_after(response: httpx.Response) -> Optional[float]:
        """
        Parse Retry-After header from response.
        
        Args:
            response: HTTP response
            
        Returns:
            Delay in seconds, or None if no valid header
        """
        retry_after = response.headers.get("Retry-After")
        
        if not retry_after:
            return None
        
        try:
            # Try to parse as integer (seconds)
            return float(retry_after)
        except ValueError:
            # Might be HTTP date format - not implemented yet
            logger.warning(
                "Cannot parse Retry-After header",
                value=retry_after,
            )
            return None
    
    @staticmethod
    async def wait_if_needed(response: httpx.Response) -> None:
        """
        Wait if Retry-After header is present.
        
        Args:
            response: HTTP response
        """
        if response.status_code == 429:
            delay = RetryAfterHandler.parse_retry_after(response)
            
            if delay:
                logger.info(f"Waiting {delay}s due to Retry-After header")
                await asyncio.sleep(delay)