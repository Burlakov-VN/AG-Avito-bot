"""OAuth2 client credentials authentication for Avito API."""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.avito.ru/token/"


class AvitoAuth:
    """Manages OAuth2 token lifecycle for Avito API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.client_id = client_id or os.environ.get("AVITO_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("AVITO_CLIENT_SECRET", "")
        self._access_token: str = ""
        self._expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def token_valid(self) -> bool:
        return bool(self._access_token and time.time() < self._expires_at)

    def get_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        if self.token_valid:
            return self._access_token

        if not self.is_configured:
            raise ValueError(
                "AVITO_CLIENT_ID and AVITO_CLIENT_SECRET must be set. "
                "Get credentials at https://developers.avito.ru/"
            )

        self._refresh_token()
        return self._access_token

    def _refresh_token(self) -> None:
        """Request a new access token from Avito OAuth2 endpoint."""
        logger.info("Requesting new Avito access token")

        response = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        self._access_token = data["access_token"]
        # Expire 5 minutes early to avoid edge cases
        expires_in = data.get("expires_in", 86400)
        self._expires_at = time.time() + expires_in - 300

        logger.info("Avito access token obtained, expires in %d seconds", expires_in)

    def auth_headers(self) -> dict[str, str]:
        """Return authorization headers for API requests."""
        return {"Authorization": f"Bearer {self.get_token()}"}
