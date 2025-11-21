"""Fetch on-chain balances for EVM and Solana wallets via Alchemy RPC APIs."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Tuple, List, Optional, TYPE_CHECKING

import httpx

from app.config import config

if TYPE_CHECKING:
    from app.services.price_service import PriceService


class DexBalanceService:
    def __init__(self, price_service: Optional["PriceService"] = None) -> None:
        sources = config.get("dex_sources", {}) or {}
        alchemy = sources.get("alchemy", {})
        self.rpc_urls: Dict[str, str] = alchemy.get("api_keys", {}) or {}
        self.wallets: Dict[str, Dict[str, str]] = alchemy.get("wallets", {}) or {}
        self.tokens: Dict[str, Dict[str, Dict]] = alchemy.get("tokens", {}) or {}
        self.timeout = httpx.Timeout(15.0)
        pricing_cfg = config.get("pricing", {}).get("coingecko", {}) or {}
        self.price_ids: Dict[str, str] = {
            str(symbol).upper(): str(price_id)
            for symbol, price_id in (pricing_cfg.get("dex_price_ids") or {}).items()
            if price_id
        }
        self._price_service = price_service

    async def fetch_all_balances(self) -> Dict[str, Dict]:
        """Fetch balances for all configured chains and wallets."""
        tasks: List[asyncio.Task] = []

        for chain_name in self.wallets.keys():
            if chain_name == "solana":
                tasks.append(asyncio.create_task(self._fetch_solana_chain()))
            else:
                tasks.append(asyncio.create_task(self._fetch_evm_chain(chain_name)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        result: Dict[str, Dict] = {}
        for payload in results:
            if isinstance(payload, tuple):
                chain_name, data = payload
                result[chain_name] = data

        price_map: Dict[str, float] = {}
        if self._price_service and self.price_ids:
            fetched_prices = await self._price_service.get_prices(self.price_ids)
            price_map = {symbol.upper(): value for symbol, value in fetched_prices.items()}

        return {
            "success": True,
            "chains": result,
            "prices": price_map,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def _fetch_evm_chain(self, chain: str) -> Tuple[str, Dict]:
        rpc_url = self.rpc_urls.get(chain)
        wallets = self.wallets.get(chain, {})
        token_defs = self.tokens.get(chain, {})
        chain_wallets: Dict[str, Dict] = {}

        if not rpc_url or not wallets:
            return chain, chain_data

        contract_addresses = {
            symbol: token.get("address")
            for symbol, token in token_defs.items()
            if token.get("address")
        }
        decimals_map = {
            symbol: token.get("decimals", 18) for symbol, token in token_defs.items()
        }

        async with httpx.AsyncClient(timeout=self.timeout) as session:
            for label, address in wallets.items():
                lower_address = address.lower()
                balances: Dict[str, float] = {}

                # Native balance (if token definition is missing address)
                for symbol, token in token_defs.items():
                    if not token.get("address"):
                        value = await self._eth_get_balance(
                            session,
                            rpc_url,
                            lower_address,
                            token.get("decimals", 18),
                        )
                        balances[symbol] = value

                # Fetch ERC-20 balances in a single call
                if contract_addresses:
                    amounts = await self._eth_get_token_balances(
                        session, rpc_url, lower_address, contract_addresses
                    )
                    for symbol, hex_value in amounts.items():
                        balances[symbol] = self._from_hex(
                            hex_value, decimals_map.get(symbol, 18)
                        )

                chain_wallets[label] = {
                    "address": address,
                    "balances": balances,
                }

        return chain, {"wallets": chain_wallets}

    async def _eth_get_balance(
        self,
        session: httpx.AsyncClient,
        rpc_url: str,
        address: str,
        decimals: int,
    ) -> float:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1,
        }
        resp = await session.post(rpc_url, json=payload)
        resp.raise_for_status()
        value = resp.json().get("result", "0x0")
        return self._from_hex(value, decimals)

    async def _eth_get_token_balances(
        self,
        session: httpx.AsyncClient,
        rpc_url: str,
        address: str,
        contract_map: Dict[str, str],
    ) -> Dict[str, str]:
        payload = {
            "jsonrpc": "2.0",
            "method": "alchemy_getTokenBalances",
            "params": [address, list(contract_map.values())],
            "id": 1,
        }
        resp = await session.post(rpc_url, json=payload)
        resp.raise_for_status()
        token_balances = resp.json().get("result", {}).get("tokenBalances", [])
        result: Dict[str, str] = {}
        for entry in token_balances:
            contract = entry.get("contractAddress")
            for symbol, addr in contract_map.items():
                if addr.lower() == (contract or "").lower():
                    result[symbol] = entry.get("tokenBalance", "0x0")
        return result

    async def _fetch_solana_chain(self) -> Tuple[str, Dict]:
        rpc_url = self.rpc_urls.get("solana")
        wallets = self.wallets.get("solana", {})
        tokens = self.tokens.get("solana", {})
        chain_wallets: Dict[str, Dict] = {}

        if not rpc_url or not wallets:
            return "solana", chain_data

        async with httpx.AsyncClient(timeout=self.timeout) as session:
            for label, owner in wallets.items():
                balances: Dict[str, float] = {}

                native_token = tokens.get("SOL") or tokens.get("native")
                if native_token:
                    balances["SOL"] = await self._sol_get_balance(
                        session, rpc_url, owner, native_token.get("decimals", 9)
                    )

                for symbol, token in tokens.items():
                    account_map = token.get("account_map")
                    if not account_map:
                        continue

                    account_address = account_map.get(label)
                    if not account_address:
                        balances[symbol] = 0.0
                        continue

                    amount = await self._sol_get_token_balance(
                        session,
                        rpc_url,
                        account_address,
                        token.get("decimals", 9),
                    )
                    balances[symbol] = amount

                chain_wallets[label] = {
                    "address": owner,
                    "balances": balances,
                }

        return "solana", {"wallets": chain_wallets}

    async def _sol_get_balance(
        self,
        session: httpx.AsyncClient,
        rpc_url: str,
        owner: str,
        decimals: int,
    ) -> float:
        payload = {
            "jsonrpc": "2.0",
            "method": "getBalance",
            "params": [owner],
            "id": 1,
        }
        resp = await session.post(rpc_url, json=payload)
        resp.raise_for_status()
        value = resp.json().get("result", {}).get("value", 0)
        divisor = 10 ** decimals
        return value / divisor if divisor else float(value)

    async def _sol_get_token_balance(
        self,
        session: httpx.AsyncClient,
        rpc_url: str,
        token_account: str,
        decimals: int,
    ) -> float:
        payload = {
            "jsonrpc": "2.0",
            "method": "getTokenAccountBalance",
            "params": [token_account],
            "id": 1,
        }
        resp = await session.post(rpc_url, json=payload)
        resp.raise_for_status()
        value = resp.json().get("result", {}).get("value", {})
        ui_amount = value.get("uiAmount")
        if ui_amount is not None:
            return float(ui_amount)
        amount_str = value.get("amount")
        if amount_str is None:
            return 0.0
        divisor = 10 ** decimals
        return int(amount_str) / divisor if divisor else float(amount_str)

    def _from_hex(self, value: str, decimals: int) -> float:
        if not value:
            return 0.0
        try:
            integer = int(value, 16)
        except ValueError:
            return 0.0
        divisor = 10 ** decimals
        return integer / divisor if divisor else float(integer)

