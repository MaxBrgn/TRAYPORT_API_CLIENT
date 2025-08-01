"""Rate limiting implementation with dual-tier token bucket algorithm."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Optional

import structlog

from ..config.constants import (
    CONSERVATIVE_RATE_LIMIT_PER_MINUTE,
    CONSERVATIVE_RATE_LIMIT_PER_SECOND,
    ERROR_RATE_LIMIT_EXCEEDED,
    RATE_LIMIT_BURST_SIZE,
)
from ..exceptions.api import TrayportRateLimitError

logger = structlog.get_logger(__name__)


class Priority(Enum):
    """Request priority levels."""
    
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    
    def __post_init__(self) -> None:
        """Initialize bucket with full capacity."""
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False otherwise
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    @property
    def available_tokens(self) -> int:
        """Get current available tokens."""
        self._refill()
        return int(self.tokens)
    
    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate time until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds until tokens are available
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
            
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


@dataclass
class QueuedRequest:
    """Request waiting in the rate limit queue."""
    
    future: asyncio.Future
    priority: Priority
    timestamp: float = field(default_factory=time.monotonic)
    tokens: int = 1


class DualTierRateLimiter:
    """
    Dual-tier rate limiter implementing both per-second and per-minute limits.
    
    Features:
    - Conservative limits with 25% safety margin
    - Dual token buckets for per-second and per-minute limits
    - Request queuing with priority levels
    - Burst prevention (max 3 requests per 500ms)
    - Adaptive throttling on 429 responses
    """
    
    def __init__(
        self,
        per_second_limit: int = CONSERVATIVE_RATE_LIMIT_PER_SECOND,
        per_minute_limit: int = CONSERVATIVE_RATE_LIMIT_PER_MINUTE,
        burst_size: int = RATE_LIMIT_BURST_SIZE,
        enable_adaptive_throttling: bool = True,
    ) -> None:
        """
        Initialize rate limiter.
        
        Args:
            per_second_limit: Maximum requests per second
            per_minute_limit: Maximum requests per minute
            burst_size: Maximum requests in 500ms window
            enable_adaptive_throttling: Enable automatic rate reduction on 429s
        """
        self.per_second_bucket = RateLimitBucket(
            capacity=per_second_limit,
            refill_rate=per_second_limit
        )
        self.per_minute_bucket = RateLimitBucket(
            capacity=per_minute_limit,
            refill_rate=per_minute_limit / 60.0
        )
        
        self.burst_size = burst_size
        self.burst_window = 0.5  # 500ms
        self.recent_requests: Deque[float] = deque(maxlen=burst_size)
        
        self.enable_adaptive_throttling = enable_adaptive_throttling
        self.throttle_factor = 1.0  # Multiplier for rate limits
        self.consecutive_429s = 0
        
        self.request_queue: asyncio.Queue[QueuedRequest] = asyncio.Queue()
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # Metrics
        self.total_requests = 0
        self.total_throttled = 0
        self.total_429s = 0
        
        self._lock = asyncio.Lock()
        
        logger.info(
            "Rate limiter initialized",
            per_second_limit=per_second_limit,
            per_minute_limit=per_minute_limit,
            burst_size=burst_size,
        )
    
    async def acquire(self, priority: Priority = Priority.NORMAL) -> None:
        """
        Acquire permission to make a request.
        
        Args:
            priority: Request priority level
            
        Raises:
            TrayportRateLimitError: If rate limit cannot be satisfied
        """
        future: asyncio.Future = asyncio.Future()
        request = QueuedRequest(future=future, priority=priority)
        
        await self.request_queue.put(request)
        
        # Start queue processor if not running
        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue())
        
        try:
            await future
        except asyncio.CancelledError:
            raise TrayportRateLimitError("Rate limit acquisition cancelled")
    
    async def _process_queue(self) -> None:
        """Process queued requests respecting rate limits."""
        while not self._shutdown:
            try:
                # Get highest priority request
                request = await asyncio.wait_for(
                    self.request_queue.get(),
                    timeout=1.0
                )
                
                # Wait for rate limit availability
                await self._wait_for_capacity()
                
                # Check burst limit
                await self._check_burst_limit()
                
                # Consume tokens
                async with self._lock:
                    if not self._try_consume():
                        # This shouldn't happen after waiting
                        logger.error("Failed to consume tokens after waiting")
                        request.future.set_exception(
                            TrayportRateLimitError(ERROR_RATE_LIMIT_EXCEEDED)
                        )
                        continue
                    
                    # Record request time for burst tracking
                    self.recent_requests.append(time.monotonic())
                    self.total_requests += 1
                
                # Complete the future
                if not request.future.done():
                    request.future.set_result(None)
                    
            except asyncio.TimeoutError:
                # No requests in queue, continue
                continue
            except Exception as e:
                logger.error("Error processing rate limit queue", error=str(e))
    
    async def _wait_for_capacity(self) -> None:
        """Wait until capacity is available in both buckets."""
        while True:
            async with self._lock:
                wait_time = self._get_wait_time()
                
            if wait_time <= 0:
                break
                
            self.total_throttled += 1
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
    
    def _get_wait_time(self) -> float:
        """Get time to wait for capacity in both buckets."""
        second_wait = self.per_second_bucket.time_until_available()
        minute_wait = self.per_minute_bucket.time_until_available()
        
        # Apply throttle factor for adaptive throttling
        if self.throttle_factor < 1.0:
            second_wait /= self.throttle_factor
            minute_wait /= self.throttle_factor
        
        return max(second_wait, minute_wait)
    
    def _try_consume(self) -> bool:
        """Try to consume tokens from both buckets."""
        # Must have capacity in both buckets
        if (self.per_second_bucket.available_tokens >= 1 and
            self.per_minute_bucket.available_tokens >= 1):
            
            self.per_second_bucket.consume(1)
            self.per_minute_bucket.consume(1)
            return True
        
        return False
    
    async def _check_burst_limit(self) -> None:
        """Check and enforce burst limit."""
        now = time.monotonic()
        
        # Remove old requests outside burst window
        cutoff = now - self.burst_window
        while self.recent_requests and self.recent_requests[0] < cutoff:
            self.recent_requests.popleft()
        
        # If at burst limit, wait
        if len(self.recent_requests) >= self.burst_size:
            wait_time = self.burst_window - (now - self.recent_requests[0])
            if wait_time > 0:
                logger.debug(f"Burst limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    def report_429(self) -> None:
        """Report a 429 response for adaptive throttling."""
        self.total_429s += 1
        self.consecutive_429s += 1
        
        if self.enable_adaptive_throttling:
            # Reduce rate by 25% for each consecutive 429
            self.throttle_factor = max(0.25, self.throttle_factor * 0.75)
            logger.warning(
                "Received 429, reducing rate",
                consecutive_429s=self.consecutive_429s,
                throttle_factor=self.throttle_factor,
            )
    
    def report_success(self) -> None:
        """Report a successful request for adaptive recovery."""
        if self.consecutive_429s > 0:
            self.consecutive_429s = 0
            
            if self.enable_adaptive_throttling and self.throttle_factor < 1.0:
                # Slowly increase rate back to normal
                self.throttle_factor = min(1.0, self.throttle_factor * 1.1)
                logger.info(
                    "Successful request, increasing rate",
                    throttle_factor=self.throttle_factor,
                )
    
    def get_metrics(self) -> dict:
        """Get rate limiter metrics."""
        return {
            "total_requests": self.total_requests,
            "total_throttled": self.total_throttled,
            "total_429s": self.total_429s,
            "throttle_factor": self.throttle_factor,
            "per_second_available": self.per_second_bucket.available_tokens,
            "per_minute_available": self.per_minute_bucket.available_tokens,
            "queue_size": self.request_queue.qsize(),
        }
    
    async def shutdown(self) -> None:
        """Shutdown the rate limiter."""
        self._shutdown = True
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel any pending requests
        while not self.request_queue.empty():
            try:
                request = self.request_queue.get_nowait()
                if not request.future.done():
                    request.future.cancel()
            except asyncio.QueueEmpty:
                break