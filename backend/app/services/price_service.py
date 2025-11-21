"""Price service for fetching external token prices."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.config import config

logger = logging.getLogger(__name__)


class PriceService:
    """Service responsible for retrieving token prices from external providers."""

    def __init__(self) -> None:
        cg_config: Dict[str, Any] = config.get("pricing.coingecko", {}) or {}

        self.enabled: bool = cg_config.get("enabled", False)
        self.base_url: str = cg_config.get(
            "base_url", "https://pro-api.coingecko.com/api/v3"
        )
        self.api_key: Optional[str] = cg_config.get("api_key")
        self.contract_address: str = (
            cg_config.get("contract_address", "").lower().strip()
        )
        self.vs_currency: str = cg_config.get("vs_currency", "usd")
        self.timeout: float = float(cg_config.get("timeout", 5))
        self.asset_symbol: str = cg_config.get("asset_symbol", "ALI").upper()

    async def get_ali_price(self) -> Optional[Dict[str, Any]]:
        """Fetch the ALI token price in USD from CoinGecko Pro API."""
        if not self.enabled:
            logger.debug("Price service disabled via configuration")
            return None

        if not self.api_key:
            logger.warning("CoinGecko API key not configured; skipping price fetch")
            return None

        if not self.contract_address:
            logger.error("CoinGecko contract address not configured")
            return None

        endpoint = f"{self.base_url.rstrip('/')}/simple/token_price/ethereum"
        params = {
            "contract_addresses": self.contract_address,
            "vs_currencies": self.vs_currency,
        }
        headers = {"x-cg-pro-api-key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

            token_data = data.get(self.contract_address)
            if not token_data:
                logger.error(
                    "CoinGecko response missing contract %s", self.contract_address
                )
                return None

            price_value = token_data.get(self.vs_currency)
            if price_value is None:
                logger.error(
                    "CoinGecko response missing %s price for contract %s",
                    self.vs_currency,
                    self.contract_address,
                )
                return None

            timestamp = datetime.utcnow().isoformat() + "Z"
            logger.info(
                "Fetched ALI price %.8f %s from CoinGecko at %s",
                price_value,
                self.vs_currency.upper(),
                timestamp,
            )

            return {
                "asset": self.asset_symbol,
                "price_usd": float(price_value),
                "source": "coingecko",
                "timestamp": timestamp,
            }

        except httpx.HTTPError as exc:
            logger.error("Failed to fetch ALI price from CoinGecko: %s", str(exc))
            return None


    async def get_prices(self, symbol_to_id: Dict[str, str]) -> Dict[str, float]:
        """Fetch USD prices for arbitrary CoinGecko IDs."""
        if not symbol_to_id:
            return {}

        if not self.enabled:
            logger.debug("Price service disabled; returning empty price map")
            return {}

        if not self.api_key:
            logger.warning(
                "CoinGecko API key not configured; cannot fetch additional prices"
            )
            return {}

        endpoint = f"{self.base_url.rstrip('/')}/simple/price"
        ids_value = ",".join(sorted(set(symbol_to_id.values())))
        params = {
            "ids": ids_value,
            "vs_currencies": self.vs_currency,
        }
        headers = {"x-cg-pro-api-key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch prices from CoinGecko: %s", str(exc))
            return {}

        prices: Dict[str, float] = {}
        for symbol, price_id in symbol_to_id.items():
            price_entry = data.get(price_id)
            if price_entry and self.vs_currency in price_entry:
                prices[symbol] = float(price_entry[self.vs_currency])
        return prices
