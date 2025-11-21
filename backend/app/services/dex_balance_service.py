"""Service for fetching on-chain balances used by the DEX ledger."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

import httpx
from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient

from app.config import config
from app.services.price_service import PriceService

getcontext().prec = 50

BALANCE_OF_SELECTOR = "0x70a08231"


@dataclass
class TokenConfig:
    symbol: str
    decimals: int
    address: Optional[str] = None
    price_symbol: Optional[str] = None
    price_id: Optional[str] = None
    fixed_price: Optional[float] = None
    native: bool = False
    spl_mint: Optional[str] = None


class DexBalanceService:
    """Loads balances for configured EVM and Solana wallets."""

    def __init__(self) -> None:
        self.config = config.get("dex", {}) or {}
        self.evm_chains: Dict[str, Dict[str, Any]] = self.config.get("evm", {})
        self.solana_config: Dict[str, Any] = self.config.get("solana") or {}
        self.rpc_timeout = self.config.get("rpc_timeout", 10)
        self.price_service = PriceService()

        (
            self.price_symbols,
            self.fixed_price_symbols,
        ) = self._collect_price_symbols()

    def _collect_price_symbols(self) -> Tuple[Dict[str, str], Dict[str, float]]:
        """Gather unique price symbols and fixed prices from token config."""
        price_targets: Dict[str, str] = {}
        fixed_symbols: Dict[str, float] = {}

        def update_from_tokens(tokens: Dict[str, Any]) -> None:
            for symbol, raw_cfg in tokens.items():
                price_symbol = raw_cfg.get("price_symbol", symbol)
                price_id = raw_cfg.get("price_id")
                fixed_price = raw_cfg.get("fixed_price")
                if fixed_price is not None:
                    fixed_symbols[price_symbol] = float(fixed_price)
                elif price_id:
                    price_targets.setdefault(price_symbol, price_id)

        for chain_cfg in self.evm_chains.values():
            update_from_tokens(chain_cfg.get("tokens", {}))
        if self.solana_config:
            update_from_tokens(self.solana_config.get("tokens", {}))

        return price_targets, fixed_symbols

    async def fetch_all_balances(self) -> Dict[str, Any]:
        """Fetch balances for all configured chains."""
        chain_results: Dict[str, Any] = {}
        tasks: List[asyncio.Task] = []

        for chain_name, chain_cfg in self.evm_chains.items():
            tasks.append(
                asyncio.create_task(
                    self._fetch_evm_chain(chain_name, chain_cfg),
                    name=f"evm-{chain_name}",
                )
            )

        if self.solana_config:
            tasks.append(
                asyncio.create_task(
                    self._fetch_solana_chain(), name="solana-chain"
                )
            )

        chain_payloads = await asyncio.gather(*tasks)
        for payload in chain_payloads:
            if payload:
                chain_results[payload["name"]] = payload["data"]

        prices = await self._build_price_map()
        return {
            "chains": chain_results,
            "prices": prices,
        }

    async def _fetch_evm_chain(
        self, chain_name: str, chain_cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        rpc_url: str = chain_cfg["rpc_url"]
        wallets: Dict[str, str] = chain_cfg.get("wallets", {})
        tokens_cfg: Dict[str, Any] = chain_cfg.get("tokens", {})
        tokens = {
            symbol: TokenConfig(
                symbol=symbol,
                decimals=int(cfg.get("decimals", 18)),
                address=(cfg.get("address") or "").lower() if cfg.get("address") else None,
                price_symbol=cfg.get("price_symbol", symbol),
                price_id=cfg.get("price_id"),
                fixed_price=cfg.get("fixed_price"),
                native=cfg.get("native", False),
            )
            for symbol, cfg in tokens_cfg.items()
        }

        async with httpx.AsyncClient(timeout=self.rpc_timeout) as client:
            chain_data: Dict[str, Any] = {"wallets": {}}
            for label, address in wallets.items():
                addr = address.lower()
                balances = await self._fetch_wallet_tokens(
                    client, rpc_url, addr, tokens
                )
                chain_data["wallets"][label] = {
                    "address": address,
                    "balances": balances,
                }

        return {"name": chain_name, "data": chain_data}

    async def _fetch_wallet_tokens(
        self,
        client: httpx.AsyncClient,
        rpc_url: str,
        wallet_address: str,
        tokens: Dict[str, TokenConfig],
    ) -> Dict[str, float]:
        results: Dict[str, float] = {}
        tasks = []
        for symbol, token_cfg in tokens.items():
            if token_cfg.native:
                tasks.append(
                    asyncio.create_task(
                        self._fetch_native_balance(
                            client, rpc_url, wallet_address, token_cfg
                        )
                    )
                )
            else:
                tasks.append(
                    asyncio.create_task(
                        self._fetch_erc20_balance(
                            client, rpc_url, wallet_address, token_cfg
                        )
                    )
                )

        balances = await asyncio.gather(*tasks)
        for symbol, amount in balances:
            results[symbol] = amount
        return results

    async def _rpc_call(
        self,
        client: httpx.AsyncClient,
        rpc_url: str,
        method: str,
        params: List[Any],
    ) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")

    async def _fetch_native_balance(
        self,
        client: httpx.AsyncClient,
        rpc_url: str,
        wallet_address: str,
        token_cfg: TokenConfig,
    ) -> Tuple[str, float]:
        result = await self._rpc_call(
            client, rpc_url, "eth_getBalance", [wallet_address, "latest"]
        )
        amount = self._normalize_hex_value(result, token_cfg.decimals)
        return token_cfg.symbol, amount

    async def _fetch_erc20_balance(
        self,
        client: httpx.AsyncClient,
        rpc_url: str,
        wallet_address: str,
        token_cfg: TokenConfig,
    ) -> Tuple[str, float]:
        if not token_cfg.address:
            return token_cfg.symbol, 0.0
        data = (
            f"{BALANCE_OF_SELECTOR}"
            f"{'0' * 24}{wallet_address.removeprefix('0x')}"
        )
        payload = {
            "to": token_cfg.address,
            "data": data,
        }
        result = await self._rpc_call(
            client, rpc_url, "eth_call", [payload, "latest"]
        )
        amount = self._normalize_hex_value(result, token_cfg.decimals)
        return token_cfg.symbol, amount

    def _normalize_hex_value(self, value: Any, decimals: int) -> float:
        if not value:
            return 0.0
        try:
            integer = int(value, 16)
        except ValueError:
            integer = 0
        scaled = Decimal(integer) / (Decimal(10) ** decimals)
        return float(scaled)

    async def _fetch_solana_chain(self) -> Optional[Dict[str, Any]]:
        rpc_url = self.solana_config.get("rpc_url")
        if not rpc_url:
            return None

        wallets: Dict[str, str] = self.solana_config.get("wallets", {})
        tokens_cfg: Dict[str, Any] = self.solana_config.get("tokens", {})
        tokens = {
            symbol: TokenConfig(
                symbol=symbol,
                decimals=int(cfg.get("decimals", 9)),
                native=cfg.get("native", False),
                price_symbol=cfg.get("price_symbol", symbol),
                price_id=cfg.get("price_id"),
                fixed_price=cfg.get("fixed_price"),
                spl_mint=cfg.get("mint"),
            )
            for symbol, cfg in tokens_cfg.items()
        }

        chain_data: Dict[str, Any] = {"wallets": {}}
        client = AsyncClient(rpc_url, timeout=self.rpc_timeout)
        try:
            for label, address in wallets.items():
                wallet_key = PublicKey(address)
                balances: Dict[str, float] = {}
                for symbol, token_cfg in tokens.items():
                    if token_cfg.native:
                        resp = await client.get_balance(wallet_key)
                        lamports = resp.value if resp.value else 0
                        amount = (
                            Decimal(lamports)
                            / (Decimal(10) ** token_cfg.decimals)
                        )
                    else:
                        amount = await self._fetch_spl_balance(
                            client, wallet_key, token_cfg
                        )
                    balances[symbol] = float(amount)

                chain_data["wallets"][label] = {
                    "address": address,
                    "balances": balances,
                }
        finally:
            await client.close()

        return {"name": "solana", "data": chain_data}

    async def _fetch_spl_balance(
        self,
        client: AsyncClient,
        owner: PublicKey,
        token_cfg: TokenConfig,
    ) -> Decimal:
        if not token_cfg.spl_mint:
            return Decimal(0)
        mint = PublicKey(token_cfg.spl_mint)
        resp = await client.get_token_accounts_by_owner(owner, mint=mint)
        total_amount = 0
        for entry in resp.value or []:
            parsed_data = entry.account.data.parsed
            token_amount = parsed_data["info"]["tokenAmount"]["amount"]
            total_amount += int(token_amount)
        return Decimal(total_amount) / (Decimal(10) ** token_cfg.decimals)

    async def _build_price_map(self) -> Dict[str, float]:
        """Fetch USD prices for all configured assets."""
        prices: Dict[str, float] = {}
        if self.price_symbols:
            fetched = await self.price_service.get_prices(self.price_symbols)
            prices.update(fetched)

        prices.update(self.fixed_price_symbols)
        return prices

