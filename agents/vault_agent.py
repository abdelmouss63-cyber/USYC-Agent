"""
USYC Protocol Labs - Vault Agent
Handles DeFi operations: deposit, withdraw, and auto-compound.
Integrates with Circle Gateway for USDC payments and x402 for autonomous service payments.
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from decimal import Decimal
import time

from web3 import Web3
from web3.exceptions import ContractLogicError

from .base_agent import BaseAgent
from .event_bus import EventType, event_bus
from .gateway_client import CircleGatewayClient, CircleGatewayError
from .x402_handler import X402Handler, X402PaymentError
from config import settings


# YieldVaultV2Upgradeable ABI (minimal for required functions)
VAULT_ABI = [
    {
        "inputs": [{"name": "assets", "type": "uint256"}],
        "name": "deposit",
        "outputs": [{"name": "shares", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "shares", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [{"name": "assets", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "shares", "type": "uint256"}],
        "name": "convertToAssets",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "compound",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# ERC20 ABI for USDC
ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class VaultAgent(BaseAgent):
    """
    Agent for interacting with the YieldVaultV2Upgradeable contract.
    Implements guardrails for safe operation.
    Integrates Circle Gateway and x402 for autonomous payments.
    """

    def __init__(
        self,
        demo_mode: bool = False,
        circle_wallet_id: Optional[str] = None,
        max_auto_payment: float = 10.0,
    ):
        """
        Initialize the Vault Agent.

        Args:
            demo_mode: If True, simulate transactions without blockchain
            circle_wallet_id: Circle wallet ID for Gateway payments
            max_auto_payment: Maximum amount for autonomous x402 payments
        """
        super().__init__(name="VaultAgent")
        self.demo_mode = demo_mode
        self._last_action_time: Dict[str, float] = {}
        self._demo_balance: int = 0  # Simulated vault shares in demo mode
        self._demo_usdc_balance: int = 1000 * 10**6  # 1000 USDC in demo

        # Initialize Circle Gateway client
        self.gateway = CircleGatewayClient(demo_mode=demo_mode)
        self.circle_wallet_id = circle_wallet_id or "demo-wallet-001"

        # Initialize x402 handler for autonomous payments
        self.x402_handler: Optional[X402Handler] = None
        self.max_auto_payment = max_auto_payment

        if not demo_mode and settings.is_configured:
            self._init_web3()
        else:
            self.w3 = None
            self.vault_contract = None
            self.usdc_contract = None
            self.account = None

    def _init_web3(self) -> None:
        """Initialize Web3 connection and contracts."""
        self.w3 = Web3(Web3.HTTPProvider(settings.arc_rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {settings.arc_rpc_url}")

        self.account = self.w3.eth.account.from_key(settings.private_key)
        self.vault_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(settings.vault_contract),
            abi=VAULT_ABI
        )

        if settings.usdc_contract:
            self.usdc_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(settings.usdc_contract),
                abi=ERC20_ABI
            )

        # Initialize x402 handler with real wallet address
        self.x402_handler = X402Handler(
            gateway_client=self.gateway,
            source_wallet_id=self.circle_wallet_id,
            payer_address=self.account.address,
            max_auto_payment=self.max_auto_payment,
            demo_mode=False,
        )

    async def _on_start(self) -> None:
        """Initialize x402 handler on agent start."""
        if self.demo_mode:
            self.x402_handler = X402Handler(
                gateway_client=self.gateway,
                source_wallet_id=self.circle_wallet_id,
                payer_address="0xDemoAddress",
                max_auto_payment=self.max_auto_payment,
                demo_mode=True,
            )
        print(f"[{self.name}] Circle Gateway and x402 handler initialized")

    async def _on_stop(self) -> None:
        """Cleanup on agent stop."""
        await self.gateway.close()
        if self.x402_handler:
            await self.x402_handler.close()

    async def _register_handlers(self) -> None:
        """Register event handlers."""
        pass  # Vault agent is a producer, not a consumer

    def _check_cooldown(self, action: str) -> bool:
        """
        Check if enough time has passed since last action.

        Args:
            action: The action type (deposit, withdraw, compound)

        Returns:
            True if action is allowed, False if in cooldown
        """
        now = time.time()
        last_time = self._last_action_time.get(action, 0)
        return (now - last_time) >= settings.cooldown_seconds

    def _update_cooldown(self, action: str) -> None:
        """Update the last action timestamp."""
        self._last_action_time[action] = time.time()

    def _to_usdc_units(self, amount: float) -> int:
        """Convert human-readable USDC to contract units (6 decimals)."""
        return int(Decimal(str(amount)) * Decimal(10**settings.usdc_decimals))

    def _from_usdc_units(self, amount: int) -> float:
        """Convert contract units to human-readable USDC."""
        return float(Decimal(amount) / Decimal(10**settings.usdc_decimals))

    # --- Gateway Payment Methods ---

    async def transfer_usdc_via_gateway(
        self,
        destination_address: str,
        amount: float,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Transfer USDC using Circle Gateway.

        Args:
            destination_address: Recipient blockchain address
            amount: Amount of USDC to transfer
            metadata: Optional transaction metadata

        Returns:
            Transfer result dictionary
        """
        print(f"[{self.name}] Initiating Gateway transfer: {amount} USDC to {destination_address[:10]}...")

        try:
            transfer = await self.gateway.transfer_usdc(
                destination_address=destination_address,
                amount=amount,
                source_wallet_id=self.circle_wallet_id,
                chain="ARC",
                metadata=metadata,
            )

            # Wait for completion
            completed = await self.gateway.wait_for_transfer_completion(transfer.id)

            result = {
                "transfer_id": completed.id,
                "tx_hash": completed.tx_hash,
                "amount": amount,
                "destination": destination_address,
                "status": completed.status.value,
            }

            await self.emit(EventType.DEPOSIT_COMPLETED, {
                "type": "gateway_transfer",
                **result,
                "timestamp": datetime.utcnow().isoformat()
            })

            print(f"[{self.name}] Gateway transfer completed: {completed.tx_hash}")
            return result

        except CircleGatewayError as e:
            await self.emit(EventType.DEPOSIT_FAILED, {
                "type": "gateway_transfer",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise

    async def get_gateway_balance(self) -> Dict[str, float]:
        """
        Get Circle Gateway wallet balance.

        Returns:
            Dictionary of currency -> balance
        """
        return await self.gateway.get_wallet_balance(self.circle_wallet_id)

    # --- x402 Autonomous Payment Methods ---

    async def access_paid_service(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict] = None,
    ) -> Any:
        """
        Access a potentially paywalled service with automatic x402 payment.

        If the service returns HTTP 402, the agent automatically:
        1. Parses the payment requirements
        2. Pays the required amount via Circle Gateway
        3. Retries the request with payment proof

        Args:
            url: Service URL
            method: HTTP method
            headers: Optional request headers
            json_data: Optional JSON body

        Returns:
            Service response data

        Raises:
            X402PaymentError: If payment or access fails
        """
        if not self.x402_handler:
            raise RuntimeError("x402 handler not initialized")

        print(f"[{self.name}] Accessing service: {url}")

        try:
            result = await self.x402_handler.pay_and_access(
                url=url,
                method=method,
                headers=headers,
                json_data=json_data,
            )
            print(f"[{self.name}] Service access successful")
            return result

        except X402PaymentError as e:
            print(f"[{self.name}] x402 payment error: {e}")
            raise

    async def fetch_with_auto_payment(
        self,
        url: str,
        method: str = "GET",
        auto_pay: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Fetch a URL with optional automatic 402 payment handling.

        Args:
            url: URL to fetch
            method: HTTP method
            auto_pay: Whether to automatically pay on 402
            **kwargs: Additional arguments

        Returns:
            Response data with payment info if applicable
        """
        if not self.x402_handler:
            raise RuntimeError("x402 handler not initialized")

        status, headers, body = await self.x402_handler.fetch_with_payment(
            url=url,
            method=method,
            auto_pay=auto_pay,
            **kwargs,
        )

        return {
            "status": status,
            "headers": dict(headers),
            "body": body,
            "payment_made": status != 402 and auto_pay,
        }

    def get_payment_history(self) -> Dict[str, Any]:
        """
        Get history of autonomous x402 payments.

        Returns:
            Payment history and statistics
        """
        if not self.x402_handler:
            return {"payments": [], "total_spent": 0}

        history = self.x402_handler.get_payment_history()
        total = self.x402_handler.get_total_spent()

        return {
            "payments": history,
            "total_spent": total,
            "payment_count": len(history),
        }

    # --- Original Vault Methods ---

    async def deposit(self, amount: float) -> Dict[str, Any]:
        """
        Deposit USDC into the vault.

        Args:
            amount: Amount of USDC to deposit

        Returns:
            Transaction result dictionary
        """
        # Guardrail: Check amount limits
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        if amount > settings.max_deposit_amount:
            raise ValueError(f"Deposit amount exceeds maximum ({settings.max_deposit_amount} USDC)")

        # Guardrail: Check cooldown
        if not self._check_cooldown("deposit"):
            raise ValueError(f"Deposit in cooldown. Please wait {settings.cooldown_seconds} seconds between actions.")

        await self.emit(EventType.DEPOSIT_INITIATED, {
            "amount": amount,
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            if self.demo_mode:
                result = await self._demo_deposit(amount)
            else:
                result = await self._execute_deposit(amount)

            self._update_cooldown("deposit")

            await self.emit(EventType.DEPOSIT_COMPLETED, {
                "amount": amount,
                "tx_hash": result.get("tx_hash"),
                "shares_received": result.get("shares_received"),
                "timestamp": datetime.utcnow().isoformat()
            })

            return result

        except Exception as e:
            await self.emit(EventType.DEPOSIT_FAILED, {
                "amount": amount,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise

    async def _demo_deposit(self, amount: float) -> Dict[str, Any]:
        """Simulate a deposit in demo mode."""
        await asyncio.sleep(0.5)  # Simulate network delay

        units = self._to_usdc_units(amount)
        if units > self._demo_usdc_balance:
            raise ValueError("Insufficient USDC balance")

        self._demo_usdc_balance -= units
        shares = units  # 1:1 for demo
        self._demo_balance += shares

        return {
            "tx_hash": f"0x{'demo' * 16}",
            "shares_received": self._from_usdc_units(shares),
            "demo": True
        }

    async def _execute_deposit(self, amount: float) -> Dict[str, Any]:
        """Execute actual deposit on blockchain."""
        units = self._to_usdc_units(amount)

        # Check USDC balance
        usdc_balance = self.usdc_contract.functions.balanceOf(self.account.address).call()
        if usdc_balance < units:
            raise ValueError(f"Insufficient USDC balance. Have: {self._from_usdc_units(usdc_balance)}")

        # Check and set allowance if needed
        allowance = self.usdc_contract.functions.allowance(
            self.account.address,
            settings.vault_contract
        ).call()

        if allowance < units:
            approve_tx = self.usdc_contract.functions.approve(
                settings.vault_contract,
                units
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price
            })
            signed_approve = self.w3.eth.account.sign_transaction(approve_tx, settings.private_key)
            self.w3.eth.send_raw_transaction(signed_approve.rawTransaction)

        # Execute deposit
        deposit_tx = self.vault_contract.functions.deposit(units).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price
        })
        signed_deposit = self.w3.eth.account.sign_transaction(deposit_tx, settings.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_deposit.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "tx_hash": tx_hash.hex(),
            "shares_received": amount,  # Simplified, actual would decode logs
            "block_number": receipt['blockNumber']
        }

    async def withdraw(self, shares: float) -> Dict[str, Any]:
        """
        Withdraw USDC from the vault.

        Args:
            shares: Amount of shares to withdraw

        Returns:
            Transaction result dictionary
        """
        # Guardrail: Check amount limits
        if shares <= 0:
            raise ValueError("Withdraw amount must be positive")
        if shares > settings.max_withdraw_amount:
            raise ValueError(f"Withdraw amount exceeds maximum ({settings.max_withdraw_amount})")

        # Guardrail: Check cooldown
        if not self._check_cooldown("withdraw"):
            raise ValueError(f"Withdraw in cooldown. Please wait {settings.cooldown_seconds} seconds between actions.")

        await self.emit(EventType.WITHDRAW_INITIATED, {
            "shares": shares,
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            if self.demo_mode:
                result = await self._demo_withdraw(shares)
            else:
                result = await self._execute_withdraw(shares)

            self._update_cooldown("withdraw")

            await self.emit(EventType.WITHDRAW_COMPLETED, {
                "shares": shares,
                "tx_hash": result.get("tx_hash"),
                "assets_received": result.get("assets_received"),
                "timestamp": datetime.utcnow().isoformat()
            })

            return result

        except Exception as e:
            await self.emit(EventType.WITHDRAW_FAILED, {
                "shares": shares,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise

    async def _demo_withdraw(self, shares: float) -> Dict[str, Any]:
        """Simulate a withdraw in demo mode."""
        await asyncio.sleep(0.5)

        units = self._to_usdc_units(shares)
        if units > self._demo_balance:
            raise ValueError("Insufficient vault shares")

        self._demo_balance -= units
        self._demo_usdc_balance += units

        return {
            "tx_hash": f"0x{'demo' * 16}",
            "assets_received": shares,
            "demo": True
        }

    async def _execute_withdraw(self, shares: float) -> Dict[str, Any]:
        """Execute actual withdraw on blockchain."""
        units = self._to_usdc_units(shares)

        # Check vault balance
        vault_balance = self.vault_contract.functions.balanceOf(self.account.address).call()
        if vault_balance < units:
            raise ValueError(f"Insufficient vault shares. Have: {self._from_usdc_units(vault_balance)}")

        withdraw_tx = self.vault_contract.functions.withdraw(units).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price
        })
        signed_tx = self.w3.eth.account.sign_transaction(withdraw_tx, settings.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "tx_hash": tx_hash.hex(),
            "assets_received": shares,
            "block_number": receipt['blockNumber']
        }

    async def compound(self) -> Dict[str, Any]:
        """
        Trigger auto-compound of yields.

        Returns:
            Transaction result dictionary
        """
        if not self._check_cooldown("compound"):
            raise ValueError(f"Compound in cooldown. Please wait {settings.cooldown_seconds} seconds between actions.")

        await self.emit(EventType.COMPOUND_INITIATED, {
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            if self.demo_mode:
                result = await self._demo_compound()
            else:
                result = await self._execute_compound()

            self._update_cooldown("compound")

            await self.emit(EventType.COMPOUND_COMPLETED, {
                "tx_hash": result.get("tx_hash"),
                "timestamp": datetime.utcnow().isoformat()
            })

            return result

        except Exception as e:
            await self.emit(EventType.COMPOUND_FAILED, {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise

    async def _demo_compound(self) -> Dict[str, Any]:
        """Simulate compound in demo mode."""
        await asyncio.sleep(0.5)

        # Simulate 0.1% yield
        yield_amount = int(self._demo_balance * 0.001)
        self._demo_balance += yield_amount

        return {
            "tx_hash": f"0x{'demo' * 16}",
            "yield_compounded": self._from_usdc_units(yield_amount),
            "demo": True
        }

    async def _execute_compound(self) -> Dict[str, Any]:
        """Execute actual compound on blockchain."""
        compound_tx = self.vault_contract.functions.compound().build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 300000,
            'gasPrice': self.w3.eth.gas_price
        })
        signed_tx = self.w3.eth.account.sign_transaction(compound_tx, settings.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "tx_hash": tx_hash.hex(),
            "block_number": receipt['blockNumber']
        }

    async def get_balance(self) -> Dict[str, Any]:
        """
        Get current vault balance.

        Returns:
            Balance information dictionary
        """
        if self.demo_mode:
            gateway_balance = await self.get_gateway_balance()
            return {
                "vault_shares": self._from_usdc_units(self._demo_balance),
                "usdc_balance": self._from_usdc_units(self._demo_usdc_balance),
                "gateway_balance": gateway_balance,
                "demo": True
            }

        vault_balance = self.vault_contract.functions.balanceOf(self.account.address).call()
        usdc_balance = self.usdc_contract.functions.balanceOf(self.account.address).call()

        # Convert shares to assets
        assets_value = 0
        if vault_balance > 0:
            assets_value = self.vault_contract.functions.convertToAssets(vault_balance).call()

        # Get Gateway balance
        gateway_balance = await self.get_gateway_balance()

        return {
            "vault_shares": self._from_usdc_units(vault_balance),
            "vault_value_usdc": self._from_usdc_units(assets_value),
            "usdc_balance": self._from_usdc_units(usdc_balance),
            "gateway_balance": gateway_balance,
            "address": self.account.address
        }
