"""
USYC Protocol Labs - FastAPI Server
REST API for vault operations with x402 autonomous payment support.
"""
import asyncio
import base64
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents import VaultAgent, MediaAgent, EventBus
from agents.x402_handler import (
    create_402_response_headers,
    verify_payment_proof,
    PaymentProof,
)
from config import settings


# Request/Response Models
class DepositRequest(BaseModel):
    """Request model for deposit endpoint."""
    amount: float = Field(..., gt=0, le=settings.max_deposit_amount, description="Amount of USDC to deposit")


class WithdrawRequest(BaseModel):
    """Request model for withdraw endpoint."""
    shares: float = Field(..., gt=0, le=settings.max_withdraw_amount, description="Amount of shares to withdraw")


class TransferRequest(BaseModel):
    """Request model for Gateway transfer endpoint."""
    destination_address: str = Field(..., description="Recipient blockchain address")
    amount: float = Field(..., gt=0, description="Amount of USDC to transfer")


class AccessPaidServiceRequest(BaseModel):
    """Request model for accessing paid services."""
    url: str = Field(..., description="URL of the service to access")
    method: str = Field(default="GET", description="HTTP method")
    auto_pay: bool = Field(default=True, description="Automatically pay if 402 received")


class TransactionResponse(BaseModel):
    """Response model for transaction endpoints."""
    success: bool
    tx_hash: Optional[str] = None
    message: str
    data: dict = {}


class BalanceResponse(BaseModel):
    """Response model for balance endpoint."""
    vault_shares: float
    vault_value_usdc: Optional[float] = None
    usdc_balance: float
    gateway_balance: Optional[Dict[str, float]] = None
    address: Optional[str] = None
    demo: bool = False


class ReceiptInfo(BaseModel):
    """Receipt file information."""
    filename: str
    path: str
    created: str


# Paywall state (demo)
_paywall_payments: Dict[str, Dict[str, Any]] = {}
PAYWALL_RECIPIENT = "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21"  # Demo recipient


# Global agents (initialized in lifespan)
vault_agent: Optional[VaultAgent] = None
media_agent: Optional[MediaAgent] = None


def create_app(demo_mode: bool = False) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        demo_mode: If True, run in demo mode without blockchain

    Returns:
        Configured FastAPI application
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan handler."""
        global vault_agent, media_agent

        # Initialize agents
        vault_agent = VaultAgent(demo_mode=demo_mode)
        media_agent = MediaAgent()

        # Start agents
        await vault_agent.start()
        await media_agent.start()

        print(f"[API] Server started (demo_mode={demo_mode})")
        print(f"[API] x402 autonomous payments enabled")

        yield

        # Cleanup
        await vault_agent.stop()
        await media_agent.stop()
        print("[API] Server stopped")

    app = FastAPI(
        title="USYC Protocol Labs API",
        description="REST API for YieldVaultV2 operations with x402 autonomous payment support",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/swagger",  # Move Swagger UI to /swagger
        redoc_url="/redoc",   # Keep ReDoc available
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    static_path = Path(__file__).parent.parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # --- Dashboard & Health ---

    @app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
    async def dashboard():
        """Serve the main dashboard."""
        index_path = Path(__file__).parent.parent / "static" / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>USYC Protocol Labs</h1><p>Dashboard not found. Check /docs for API.</p>")

    @app.get("/docs", response_class=HTMLResponse, tags=["Documentation"])
    async def custom_docs():
        """Serve custom API documentation page."""
        docs_path = Path(__file__).parent.parent / "static" / "docs.html"
        if docs_path.exists():
            return HTMLResponse(content=docs_path.read_text(encoding="utf-8"))
        # Fallback to Swagger if custom docs not found
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/swagger")

    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "USYC Protocol Labs",
            "vault_contract": settings.vault_contract,
            "demo_mode": demo_mode,
            "features": ["vault", "gateway", "x402"]
        }

    # --- Vault Operations ---

    @app.post("/vault/deposit", response_model=TransactionResponse, tags=["Vault"])
    async def deposit(request: DepositRequest):
        """
        Deposit USDC into the vault.

        - **amount**: Amount of USDC to deposit (max: {max_deposit})
        """.format(max_deposit=settings.max_deposit_amount)
        try:
            result = await vault_agent.deposit(request.amount)
            return TransactionResponse(
                success=True,
                tx_hash=result.get("tx_hash"),
                message=f"Successfully deposited {request.amount} USDC",
                data=result
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/vault/withdraw", response_model=TransactionResponse, tags=["Vault"])
    async def withdraw(request: WithdrawRequest):
        """
        Withdraw USDC from the vault.

        - **shares**: Amount of shares to withdraw (max: {max_withdraw})
        """.format(max_withdraw=settings.max_withdraw_amount)
        try:
            result = await vault_agent.withdraw(request.shares)
            return TransactionResponse(
                success=True,
                tx_hash=result.get("tx_hash"),
                message=f"Successfully withdrew {request.shares} shares",
                data=result
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/vault/compound", response_model=TransactionResponse, tags=["Vault"])
    async def compound():
        """Trigger auto-compound of yields."""
        try:
            result = await vault_agent.compound()
            return TransactionResponse(
                success=True,
                tx_hash=result.get("tx_hash"),
                message="Successfully triggered compound",
                data=result
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/vault/balance", response_model=BalanceResponse, tags=["Vault"])
    async def get_balance():
        """Get current vault, USDC, and Gateway balance."""
        try:
            balance = await vault_agent.get_balance()
            return BalanceResponse(**balance)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- Circle Gateway Operations ---

    @app.post("/gateway/transfer", response_model=TransactionResponse, tags=["Gateway"])
    async def gateway_transfer(request: TransferRequest):
        """
        Transfer USDC via Circle Gateway.

        - **destination_address**: Recipient blockchain address
        - **amount**: Amount of USDC to transfer
        """
        try:
            result = await vault_agent.transfer_usdc_via_gateway(
                destination_address=request.destination_address,
                amount=request.amount,
            )
            return TransactionResponse(
                success=True,
                tx_hash=result.get("tx_hash"),
                message=f"Successfully transferred {request.amount} USDC",
                data=result
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/gateway/balance", tags=["Gateway"])
    async def gateway_balance():
        """Get Circle Gateway wallet balance."""
        try:
            balance = await vault_agent.get_gateway_balance()
            return {"balance": balance}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- x402 Autonomous Payments ---

    @app.post("/x402/access", tags=["x402"])
    async def access_paid_service(request: AccessPaidServiceRequest):
        """
        Access a paid service with automatic x402 payment.

        The agent will:
        1. Try to access the URL
        2. If it receives HTTP 402, automatically pay the required amount
        3. Retry the request with payment proof
        """
        try:
            result = await vault_agent.fetch_with_auto_payment(
                url=request.url,
                method=request.method,
                auto_pay=request.auto_pay,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/x402/history", tags=["x402"])
    async def payment_history():
        """Get history of autonomous x402 payments made by the agent."""
        return vault_agent.get_payment_history()

    # --- Demo Paywall Endpoint ---

    @app.get("/demo/paywall", tags=["Demo"])
    async def demo_paywall(
        request: Request,
        x_payment_proof: Optional[str] = Header(None),
        x_payment_txhash: Optional[str] = Header(None),
    ):
        """
        Demo paywalled endpoint that returns HTTP 402 Payment Required.

        This endpoint demonstrates the x402 protocol:
        1. First request returns 402 with payment requirements
        2. Client pays via Circle Gateway
        3. Retry with payment proof grants access

        Cost: 0.10 USDC
        """
        payment_amount = 0.10
        payment_id = str(uuid4())

        # Check for payment proof
        if x_payment_proof:
            is_valid, proof = verify_payment_proof(
                x_payment_proof,
                expected_amount=payment_amount,
                expected_recipient=PAYWALL_RECIPIENT,
            )

            if is_valid and proof:
                # Store payment record
                _paywall_payments[proof.tx_hash] = {
                    "amount": proof.amount,
                    "payer": proof.payer_address,
                    "timestamp": proof.timestamp.isoformat(),
                }

                # Return premium content
                return {
                    "success": True,
                    "message": "Payment verified! Welcome to the premium content.",
                    "content": {
                        "title": "Exclusive DeFi Yield Strategies",
                        "data": [
                            {"strategy": "USYC Vault Staking", "apy": "8.5%"},
                            {"strategy": "LP Farming", "apy": "12.3%"},
                            {"strategy": "Auto-Compound", "apy": "15.7%"},
                        ],
                        "premium_feature": "Real-time yield optimization alerts",
                    },
                    "payment_info": {
                        "tx_hash": proof.tx_hash,
                        "amount_paid": proof.amount,
                    }
                }

        # Also accept tx hash directly (simplified verification)
        if x_payment_txhash and x_payment_txhash in _paywall_payments:
            return {
                "success": True,
                "message": "Payment verified via tx hash!",
                "content": {
                    "title": "Premium Content Unlocked",
                    "data": "Your exclusive DeFi insights...",
                }
            }

        # Return 402 Payment Required
        headers = create_402_response_headers(
            amount=payment_amount,
            recipient_address=PAYWALL_RECIPIENT,
            currency="USDC",
            network="ARC",
            payment_id=payment_id,
            description="Access to premium DeFi yield strategies",
        )

        return JSONResponse(
            status_code=402,
            content={
                "payment_required": True,
                "amount": payment_amount,
                "currency": "USDC",
                "recipient": PAYWALL_RECIPIENT,
                "network": "ARC",
                "payment_id": payment_id,
                "description": "Access to premium DeFi yield strategies",
                "message": "Payment required to access this content. Pay 0.10 USDC to unlock.",
            },
            headers=headers,
        )

    @app.post("/demo/paywall", tags=["Demo"])
    async def demo_paywall_post(
        request: Request,
        x_payment_proof: Optional[str] = Header(None),
        x_payment_txhash: Optional[str] = Header(None),
    ):
        """POST version of the paywall endpoint for testing."""
        return await demo_paywall(request, x_payment_proof, x_payment_txhash)

    @app.get("/demo/paywall/test-auto", tags=["Demo"])
    async def test_auto_payment():
        """
        Test endpoint that makes the agent automatically pay the paywall.

        Demonstrates end-to-end autonomous commerce:
        1. Agent tries to access /demo/paywall
        2. Receives 402 Payment Required
        3. Automatically pays via Circle Gateway
        4. Gets access to premium content
        """
        try:
            # Get the base URL from settings or default
            base_url = f"http://localhost:{settings.api_port}"
            paywall_url = f"{base_url}/demo/paywall"

            print(f"[Demo] Testing autonomous payment to {paywall_url}")

            result = await vault_agent.fetch_with_auto_payment(
                url=paywall_url,
                method="GET",
                auto_pay=True,
            )

            return {
                "success": True,
                "message": "Autonomous payment test completed!",
                "result": result,
                "payment_history": vault_agent.get_payment_history(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Autonomous payment test failed",
            }

    @app.get("/demo/payments", tags=["Demo"])
    async def list_demo_payments():
        """List all payments received by the demo paywall."""
        return {
            "payments": _paywall_payments,
            "total_received": sum(p["amount"] for p in _paywall_payments.values()),
        }

    # --- Receipts ---

    @app.get("/receipts", tags=["Receipts"])
    async def list_receipts():
        """List all generated transaction receipts."""
        receipts = media_agent.list_receipts()
        return {
            "receipts": [
                {
                    "filename": r.name,
                    "path": str(r),
                    "created": r.stat().st_mtime
                }
                for r in receipts
            ]
        }

    @app.get("/receipts/{filename}", tags=["Receipts"])
    async def get_receipt(filename: str):
        """Download a specific receipt PDF."""
        receipt_path = Path("receipts") / filename
        if not receipt_path.exists():
            raise HTTPException(status_code=404, detail="Receipt not found")
        return FileResponse(
            receipt_path,
            media_type="application/pdf",
            filename=filename
        )

    # --- Events ---

    @app.get("/events", tags=["Events"])
    async def get_events(limit: int = 50):
        """Get recent events from the event bus."""
        from agents.event_bus import event_bus
        events = event_bus.get_history(limit=limit)
        return {
            "events": [e.to_dict() for e in events]
        }

    return app


# Default app instance for uvicorn
app = create_app(demo_mode=True)
