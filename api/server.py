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


def _generate_demo_page(
    title: str,
    agent_name: str,
    agent_icon: str,
    description: str,
    features: list,
    endpoints: list,
    demo_code: str,
    color: str = "electric",
    extra_content: str = ""
) -> str:
    """Generate HTML for a demo page."""
    color_map = {
        "neon": {"primary": "#2ECC71", "gradient": "from-green-500 to-emerald-500"},
        "electric": {"primary": "#3498DB", "gradient": "from-blue-500 to-cyan-500"},
        "purple": {"primary": "#9B59B6", "gradient": "from-purple-500 to-pink-500"},
        "yellow": {"primary": "#F1C40F", "gradient": "from-yellow-500 to-orange-500"},
    }
    c = color_map.get(color, color_map["electric"])

    features_html = "".join([
        f'''<div class="glass-card p-4 text-center">
            <div class="text-3xl mb-2">{f["icon"]}</div>
            <h4 class="font-semibold mb-1">{f["title"]}</h4>
            <p class="text-gray-400 text-sm">{f["desc"]}</p>
        </div>'''
        for f in features
    ])

    endpoints_html = "".join([
        f'''<div class="flex items-center gap-3 p-3 bg-navy/30 rounded-lg">
            <span class="px-2 py-1 text-xs font-mono rounded {'bg-green-500/20 text-green-400' if e["method"] == 'GET' else 'bg-blue-500/20 text-blue-400'}">{e["method"]}</span>
            <code class="text-sm text-gray-300">{e["path"]}</code>
            <span class="text-xs text-gray-500 ml-auto">{e["desc"]}</span>
        </div>'''
        for e in endpoints
    ])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | USYC Protocol Labs</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        navy: '#1E3A5F',
                        'navy-light': '#2a4a73',
                        electric: '#3498DB',
                        neon: '#2ECC71',
                        purple: '#9B59B6',
                    }},
                    fontFamily: {{
                        'space': ['Space Grotesk', 'sans-serif'],
                        'mono': ['JetBrains Mono', 'monospace'],
                    }},
                }}
            }}
        }}
    </script>
    <style>
        body {{ font-family: 'Space Grotesk', sans-serif; background: #0a0f1a; color: #fff; min-height: 100vh; }}
        .glass-card {{ background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(20px); border: 1px solid rgba(52, 152, 219, 0.2); border-radius: 16px; }}
        .gradient-text {{ background: linear-gradient(135deg, {c["primary"]} 0%, #fff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    </style>
</head>
<body>
    <div class="max-w-5xl mx-auto px-4 py-8">
        <!-- Navigation -->
        <nav class="flex items-center justify-between mb-8">
            <a href="/" class="text-gray-400 hover:text-white transition-colors flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
                Back to Dashboard
            </a>
            <div class="flex items-center gap-4">
                <a href="/docs" class="px-4 py-2 bg-electric/20 text-electric rounded-lg hover:bg-electric/30 transition-colors">API Docs</a>
                <a href="/demo/vault" class="px-3 py-2 text-sm text-gray-400 hover:text-white">Vault</a>
                <a href="/demo/media" class="px-3 py-2 text-sm text-gray-400 hover:text-white">Media</a>
                <a href="/demo/gateway" class="px-3 py-2 text-sm text-gray-400 hover:text-white">Gateway</a>
                <a href="/demo/x402" class="px-3 py-2 text-sm text-gray-400 hover:text-white">x402</a>
            </div>
        </nav>

        <!-- Header -->
        <header class="text-center mb-12">
            <div class="text-6xl mb-4">{agent_icon}</div>
            <h1 class="text-4xl font-bold mb-4 gradient-text">{agent_name}</h1>
            <p class="text-xl text-gray-400 max-w-2xl mx-auto">{description}</p>
        </header>

        <!-- Features -->
        <section class="mb-12">
            <h2 class="text-2xl font-bold mb-6">Features</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                {features_html}
            </div>
        </section>

        <!-- API Endpoints -->
        <section class="mb-12">
            <h2 class="text-2xl font-bold mb-6">API Endpoints</h2>
            <div class="glass-card p-6 space-y-3">
                {endpoints_html}
            </div>
        </section>

        <!-- Code Example -->
        <section class="mb-12">
            <h2 class="text-2xl font-bold mb-6">Example Usage</h2>
            <div class="glass-card p-6">
                <pre class="font-mono text-sm text-gray-300 overflow-x-auto"><code>{demo_code}</code></pre>
            </div>
        </section>

        {extra_content}

        <!-- Footer -->
        <footer class="text-center py-8 border-t border-gray-800 mt-12">
            <p class="text-gray-500">USYC Protocol Labs | <a href="/docs" class="text-electric hover:underline">API Documentation</a></p>
        </footer>
    </div>
</body>
</html>'''


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
        description="""
## Autonomous AI Agent for Agentic Commerce

**USYC Protocol Labs** provides a multi-agent system for DeFi yield optimization with autonomous payment capabilities.

### Features
- **Vault Agent**: DeFi vault operations (deposit, withdraw, compound)
- **Media Agent**: Automatic PDF receipt generation
- **Gateway Client**: Circle Gateway USDC transfers
- **x402 Handler**: Autonomous HTTP 402 payment handling

### Quick Links
- [Demo: Vault Agent](/demo/vault) - Test vault operations
- [Demo: Media Agent](/demo/media) - Test receipt generation
- [Demo: Gateway Client](/demo/gateway) - Test USDC transfers
- [Demo: x402 Handler](/demo/x402) - Test autonomous payments
        """,
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",  # Swagger UI at /docs
        redoc_url="/redoc",
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

    # --- Interactive Demo Pages ---

    @app.get("/demo/vault", response_class=HTMLResponse, tags=["Demo Pages"])
    async def demo_vault_page():
        """
        Interactive demo page for the Vault Agent.

        Test DeFi vault operations:
        - Deposit USDC into the yield vault
        - Withdraw shares from the vault
        - Trigger auto-compound of yields
        - View real-time balances
        """
        return HTMLResponse(content=_generate_demo_page(
            title="Vault Agent Demo",
            agent_name="Vault Agent",
            agent_icon="🏦",
            description="DeFi yield optimization with autonomous deposit, withdraw, and compound operations on the YieldVaultV2 contract.",
            features=[
                {"icon": "📥", "title": "Deposit USDC", "desc": "Deposit USDC into the vault to earn yield"},
                {"icon": "📤", "title": "Withdraw Shares", "desc": "Withdraw your shares and receive USDC"},
                {"icon": "🔄", "title": "Auto-Compound", "desc": "Reinvest yields for maximum returns"},
                {"icon": "📊", "title": "Balance Tracking", "desc": "Real-time vault and USDC balance monitoring"},
            ],
            endpoints=[
                {"method": "POST", "path": "/vault/deposit", "desc": "Deposit USDC (amount in body)"},
                {"method": "POST", "path": "/vault/withdraw", "desc": "Withdraw shares (shares in body)"},
                {"method": "POST", "path": "/vault/compound", "desc": "Trigger yield compound"},
                {"method": "GET", "path": "/vault/balance", "desc": "Get current balances"},
            ],
            demo_code='''# Deposit 100 USDC into vault
curl -X POST "/vault/deposit" \\
  -H "Content-Type: application/json" \\
  -d '{"amount": 100.0}'

# Check balance
curl "/vault/balance"

# Compound yields
curl -X POST "/vault/compound"''',
            color="neon"
        ))

    @app.get("/demo/media", response_class=HTMLResponse, tags=["Demo Pages"])
    async def demo_media_page():
        """
        Interactive demo page for the Media Agent.

        Test PDF receipt generation:
        - Automatic receipt creation on transactions
        - Branded PDF documents with QR codes
        - Transaction history tracking
        """
        return HTMLResponse(content=_generate_demo_page(
            title="Media Agent Demo",
            agent_name="Media Agent",
            agent_icon="📄",
            description="Automatic PDF receipt generation for all vault transactions. Creates branded documents with QR codes linking to Arc Explorer.",
            features=[
                {"icon": "📄", "title": "PDF Generation", "desc": "Automatic branded receipt creation"},
                {"icon": "📱", "title": "QR Codes", "desc": "Scannable links to transaction on Arc Explorer"},
                {"icon": "🎨", "title": "Custom Branding", "desc": "USYC Protocol Labs branded documents"},
                {"icon": "📁", "title": "Receipt Archive", "desc": "All receipts stored and accessible"},
            ],
            endpoints=[
                {"method": "GET", "path": "/receipts", "desc": "List all generated receipts"},
                {"method": "GET", "path": "/receipts/{filename}", "desc": "Download specific PDF"},
            ],
            demo_code='''# List all receipts
curl "/receipts"

# Download a specific receipt
curl "/receipts/deposit_2024_001.pdf" -o receipt.pdf

# Receipts are auto-generated after:
# - Deposits
# - Withdrawals
# - Compound operations''',
            color="purple"
        ))

    @app.get("/demo/gateway", response_class=HTMLResponse, tags=["Demo Pages"])
    async def demo_gateway_page():
        """
        Interactive demo page for the Circle Gateway Client.

        Test USDC transfers via Circle's payment infrastructure:
        - Send USDC to any address
        - Check wallet balance
        - View transfer history
        """
        return HTMLResponse(content=_generate_demo_page(
            title="Gateway Client Demo",
            agent_name="Circle Gateway Client",
            agent_icon="🔗",
            description="Seamless USDC transfers via Circle's programmable wallet infrastructure. Enables fast, secure payments on the Arc network.",
            features=[
                {"icon": "💸", "title": "USDC Transfers", "desc": "Send USDC to any blockchain address"},
                {"icon": "👛", "title": "Wallet Management", "desc": "Circle-managed programmable wallets"},
                {"icon": "⚡", "title": "Fast Settlement", "desc": "Near-instant transaction confirmation"},
                {"icon": "🔒", "title": "Secure Infrastructure", "desc": "Enterprise-grade Circle security"},
            ],
            endpoints=[
                {"method": "POST", "path": "/gateway/transfer", "desc": "Transfer USDC to address"},
                {"method": "GET", "path": "/gateway/balance", "desc": "Get wallet balance"},
            ],
            demo_code='''# Check Gateway wallet balance
curl "/gateway/balance"

# Transfer USDC to an address
curl -X POST "/gateway/transfer" \\
  -H "Content-Type: application/json" \\
  -d '{
    "destination_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
    "amount": 10.0
  }' ''',
            color="electric"
        ))

    @app.get("/demo/x402", response_class=HTMLResponse, tags=["Demo Pages"])
    async def demo_x402_page():
        """
        Interactive demo page for the x402 Autonomous Payment Handler.

        Test HTTP 402 Payment Required handling:
        - Automatic payment detection
        - Autonomous USDC payment execution
        - Payment proof generation and verification
        """
        return HTMLResponse(content=_generate_demo_page(
            title="x402 Handler Demo",
            agent_name="x402 Autonomous Payment Handler",
            agent_icon="⚡",
            description="Revolutionary HTTP 402 Payment Required protocol handler. AI agents automatically detect, pay, and retry when encountering paywalled content.",
            features=[
                {"icon": "🔍", "title": "402 Detection", "desc": "Automatic paywall detection from HTTP headers"},
                {"icon": "💳", "title": "Auto-Payment", "desc": "Autonomous USDC payment via Circle Gateway"},
                {"icon": "🔐", "title": "Payment Proof", "desc": "Cryptographic proof for content access"},
                {"icon": "🤖", "title": "Zero Intervention", "desc": "Fully autonomous without human approval"},
            ],
            endpoints=[
                {"method": "POST", "path": "/x402/access", "desc": "Access paywalled URL with auto-pay"},
                {"method": "GET", "path": "/x402/history", "desc": "View payment history"},
                {"method": "GET", "path": "/demo/paywall", "desc": "Test paywall (returns 402)"},
                {"method": "GET", "path": "/demo/paywall/test-auto", "desc": "Test full auto-payment flow"},
            ],
            demo_code='''# Test the full autonomous payment flow
curl "/demo/paywall/test-auto"

# Access any paywalled URL with auto-payment
curl -X POST "/x402/access" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://api.example.com/premium",
    "auto_pay": true
  }'

# View payment history
curl "/x402/history"''',
            color="yellow",
            extra_content='''
            <div class="mt-8 p-6 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 rounded-2xl border border-yellow-500/30">
                <h3 class="text-xl font-bold text-yellow-400 mb-4">🚀 Try It Now!</h3>
                <p class="text-gray-300 mb-4">Click the button below to test the autonomous payment flow:</p>
                <button onclick="testX402()" class="px-6 py-3 bg-gradient-to-r from-yellow-500 to-orange-500 rounded-xl font-semibold hover:scale-105 transition-transform">
                    Test Autonomous Payment
                </button>
                <div id="x402Result" class="mt-4 hidden p-4 bg-black/30 rounded-xl font-mono text-sm"></div>
            </div>
            <script>
            async function testX402() {
                const result = document.getElementById('x402Result');
                result.classList.remove('hidden');
                result.innerHTML = '<span class="text-yellow-400">⏳ Testing autonomous payment...</span>';
                try {
                    const res = await fetch('/demo/paywall/test-auto');
                    const data = await res.json();
                    result.innerHTML = '<span class="text-green-400">✅ Success!</span><pre class="mt-2 text-xs overflow-auto">' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (e) {
                    result.innerHTML = '<span class="text-red-400">❌ Error: ' + e.message + '</span>';
                }
            }
            </script>
            '''
        ))

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
