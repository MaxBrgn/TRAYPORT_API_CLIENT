"""Authentication handling for Trayport API."""

from typing import Dict, Optional

import httpx

from ..config.constants import API_KEY_HEADER, ERROR_INVALID_API_KEY
from ..exceptions.api import TrayportAuthenticationError


class TrayportAuth(httpx.Auth):
    """
    Authentication handler for Trayport API requests.
    
    Implements httpx.Auth interface to automatically add API key header
    to all requests.
    """

    def __init__(self, api_key: str) -> None:
        """
        Initialize authentication handler.
        
        Args:
            api_key: Trayport API key
            
        Raises:
            TrayportAuthenticationError: If API key is invalid
        """
        if not api_key or not isinstance(api_key, str):
            raise TrayportAuthenticationError(ERROR_INVALID_API_KEY)
            
        self._api_key = api_key.strip()
        if not self._api_key:
            raise TrayportAuthenticationError(ERROR_INVALID_API_KEY)

    def auth_flow(self, request: httpx.Request) -> httpx.Request:
        """
        Apply authentication to the request.
        
        Args:
            request: The request to authenticate
            
        Yields:
            The authenticated request
        """
        request.headers[API_KEY_HEADER] = self._api_key
        yield request

    @property
    def api_key(self) -> str:
        """Get the API key (for testing purposes)."""
        return self._api_key

    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers.
        
        Returns:
            Dictionary with API key header
        """
        return {API_KEY_HEADER: self._api_key}

    async def test_authentication(
        self, 
        base_url: str,
        timeout: Optional[float] = 10.0
    ) -> bool:
        """
        Test if the API key is valid by making a simple request.
        
        Args:
            base_url: Base URL of the API to test against
            timeout: Request timeout in seconds
            
        Returns:
            True if authentication is successful
            
        Raises:
            TrayportAuthenticationError: If authentication fails
        """
        try:
            async with httpx.AsyncClient(
                auth=self,
                timeout=timeout,
                follow_redirects=True
            ) as client:
                # Test with a simple endpoint that requires authentication
                response = await client.get(f"{base_url}/instruments")
                
                if response.status_code == 401:
                    raise TrayportAuthenticationError(
                        "Authentication failed: Invalid API key"
                    )
                elif response.status_code == 403:
                    raise TrayportAuthenticationError(
                        "Authentication failed: Access forbidden"
                    )
                elif response.status_code >= 400:
                    # Other client errors might not be auth-related
                    return True
                    
                return True
                
        except httpx.ConnectError as e:
            raise TrayportAuthenticationError(
                f"Failed to connect to API: {str(e)}"
            ) from e
        except httpx.TimeoutException as e:
            raise TrayportAuthenticationError(
                f"Authentication test timed out: {str(e)}"
            ) from e
        except Exception as e:
            if isinstance(e, TrayportAuthenticationError):
                raise
            raise TrayportAuthenticationError(
                f"Authentication test failed: {str(e)}"
            ) from e

    def __repr__(self) -> str:
        """String representation of the auth handler."""
        # Mask the API key for security
        masked_key = f"{self._api_key[:4]}...{self._api_key[-4:]}" if len(self._api_key) > 8 else "***"
        return f"TrayportAuth(api_key='{masked_key}')"