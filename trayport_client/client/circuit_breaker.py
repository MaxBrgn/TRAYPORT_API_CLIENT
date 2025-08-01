"""Circuit breaker pattern implementation for fault tolerance."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional, Type

import structlog

from ..config.constants import (
    DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    DEFAULT_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    ERROR_CIRCUIT_BREAKER_OPEN,
)
from ..exceptions.client import TrayportCircuitBreakerError

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    failure_threshold: int = DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT
    half_open_max_calls: int = DEFAULT_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS
    expected_exception: Type[Exception] = Exception
    
    # Optional callbacks
    on_open: Optional[Callable] = None
    on_close: Optional[Callable] = None
    on_half_open: Optional[Callable] = None


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    state_changes: Dict[str, int] = field(default_factory=dict)
    
    def reset(self) -> None:
        """Reset statistics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.consecutive_failures = 0
        self.last_failure_time = None
        self.state_changes.clear()
    
    def record_success(self) -> None:
        """Record successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_failures = 0
    
    def record_failure(self) -> None:
        """Record failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
    
    def record_rejection(self) -> None:
        """Record rejected call."""
        self.rejected_calls += 1


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected
    - HALF_OPEN: Testing if service has recovered
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """
        Initialize circuit breaker.
        
        Args:
            name: Name for this circuit breaker instance
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0
        self._state_lock = asyncio.Lock()
        
        self.stats = CircuitBreakerStats()
        
        # Time when circuit was opened
        self._opened_at: Optional[float] = None
        
        logger.info(
            f"Circuit breaker '{name}' initialized",
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self._state == CircuitState.HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from function execution
            
        Raises:
            TrayportCircuitBreakerError: If circuit is open
            Exception: Any exception from func
        """
        async with self._state_lock:
            # Check if we should transition states
            await self._check_state_transition()
            
            # Handle based on current state
            if self._state == CircuitState.OPEN:
                self.stats.record_rejection()
                raise TrayportCircuitBreakerError(
                    f"{ERROR_CIRCUIT_BREAKER_OPEN}: {self.name}",
                    failure_count=self.stats.consecutive_failures,
                    last_failure_time=self.stats.last_failure_time,
                    recovery_timeout=self.config.recovery_timeout,
                )
            
            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    # Already testing maximum calls
                    self.stats.record_rejection()
                    raise TrayportCircuitBreakerError(
                        f"Circuit breaker '{self.name}' is testing recovery",
                        failure_count=self.stats.consecutive_failures,
                    )
                
                self._half_open_calls += 1
        
        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            await self._on_failure()
            raise
        except Exception:
            # Don't count unexpected exceptions as circuit failures
            raise
    
    async def _check_state_transition(self) -> None:
        """Check if state should transition."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._opened_at and (
                time.monotonic() - self._opened_at >= self.config.recovery_timeout
            ):
                await self._transition_to_half_open()
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._state_lock:
            self.stats.record_success()
            
            if self._state == CircuitState.HALF_OPEN:
                # Success in half-open state, check if we should close
                if self._half_open_calls >= self.config.half_open_max_calls:
                    await self._transition_to_closed()
    
    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._state_lock:
            self.stats.record_failure()
            
            if self._state == CircuitState.CLOSED:
                # Check if we should open
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to_open()
                    
            elif self._state == CircuitState.HALF_OPEN:
                # Failure in half-open state, reopen
                await self._transition_to_open()
    
    async def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_calls = 0
        
        self.stats.state_changes[CircuitState.OPEN.value] = (
            self.stats.state_changes.get(CircuitState.OPEN.value, 0) + 1
        )
        
        logger.warning(
            f"Circuit breaker '{self.name}' opened",
            consecutive_failures=self.stats.consecutive_failures,
            total_failures=self.stats.failed_calls,
        )
        
        if self.config.on_open:
            try:
                await self.config.on_open(self)
            except Exception as e:
                logger.error(f"Error in on_open callback: {e}")
    
    async def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0
        self.stats.consecutive_failures = 0
        
        self.stats.state_changes[CircuitState.CLOSED.value] = (
            self.stats.state_changes.get(CircuitState.CLOSED.value, 0) + 1
        )
        
        logger.info(
            f"Circuit breaker '{self.name}' closed",
            total_calls=self.stats.total_calls,
            success_rate=self._get_success_rate(),
        )
        
        if self.config.on_close:
            try:
                await self.config.on_close(self)
            except Exception as e:
                logger.error(f"Error in on_close callback: {e}")
    
    async def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        
        self.stats.state_changes[CircuitState.HALF_OPEN.value] = (
            self.stats.state_changes.get(CircuitState.HALF_OPEN.value, 0) + 1
        )
        
        logger.info(
            f"Circuit breaker '{self.name}' half-opened",
            recovery_timeout=self.config.recovery_timeout,
        )
        
        if self.config.on_half_open:
            try:
                await self.config.on_half_open(self)
            except Exception as e:
                logger.error(f"Error in on_half_open callback: {e}")
    
    def _get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.stats.total_calls == 0:
            return 0.0
        return self.stats.successful_calls / self.stats.total_calls
    
    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        async with self._state_lock:
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._half_open_calls = 0
            self.stats.reset()
            
            logger.info(f"Circuit breaker '{self.name}' reset")
    
    def get_status(self) -> dict:
        """Get circuit breaker status."""
        status = {
            "name": self.name,
            "state": self._state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "consecutive_failures": self.stats.consecutive_failures,
                "success_rate": self._get_success_rate(),
                "state_changes": self.stats.state_changes,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls,
            },
        }
        
        if self._opened_at:
            status["time_since_opened"] = time.monotonic() - self._opened_at
            
        return status


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self) -> None:
        """Initialize circuit breaker manager."""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.
        
        Args:
            name: Circuit breaker name
            config: Configuration for new circuit breaker
            
        Returns:
            Circuit breaker instance
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            
            return self._breakers[name]
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()
    
    def get_all_status(self) -> Dict[str, dict]:
        """Get status of all circuit breakers."""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }