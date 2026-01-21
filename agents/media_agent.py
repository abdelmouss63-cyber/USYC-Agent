"""
USYC Protocol Labs - Media Agent
Generates PDF receipts for vault transactions with branding.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .base_agent import BaseAgent
from .event_bus import Event, EventType
from config import settings


class MediaAgent(BaseAgent):
    """
    Agent for generating PDF receipts for vault transactions.
    Listens to vault events and creates branded receipts.
    """

    def __init__(self, output_dir: str = "receipts"):
        """
        Initialize the Media Agent.

        Args:
            output_dir: Directory to save generated receipts
        """
        super().__init__(name="MediaAgent")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Brand colors (converted from hex)
        self.brand_navy = colors.HexColor(settings.brand_navy)
        self.brand_blue = colors.HexColor(settings.brand_blue)
        self.brand_green = colors.HexColor(settings.brand_green)

    async def _register_handlers(self) -> None:
        """Register event handlers for vault events."""
        self.subscribe(EventType.DEPOSIT_COMPLETED, self._on_deposit_completed)
        self.subscribe(EventType.WITHDRAW_COMPLETED, self._on_withdraw_completed)
        self.subscribe(EventType.COMPOUND_COMPLETED, self._on_compound_completed)

    async def _on_deposit_completed(self, event: Event) -> None:
        """Handle deposit completed event."""
        receipt_path = await self.generate_receipt(
            transaction_type="Deposit",
            event_data=event.data,
            event_id=event.event_id
        )
        await self.emit(EventType.RECEIPT_GENERATED, {
            "receipt_path": str(receipt_path),
            "transaction_type": "deposit",
            "event_id": event.event_id
        })

    async def _on_withdraw_completed(self, event: Event) -> None:
        """Handle withdraw completed event."""
        receipt_path = await self.generate_receipt(
            transaction_type="Withdraw",
            event_data=event.data,
            event_id=event.event_id
        )
        await self.emit(EventType.RECEIPT_GENERATED, {
            "receipt_path": str(receipt_path),
            "transaction_type": "withdraw",
            "event_id": event.event_id
        })

    async def _on_compound_completed(self, event: Event) -> None:
        """Handle compound completed event."""
        receipt_path = await self.generate_receipt(
            transaction_type="Compound",
            event_data=event.data,
            event_id=event.event_id
        )
        await self.emit(EventType.RECEIPT_GENERATED, {
            "receipt_path": str(receipt_path),
            "transaction_type": "compound",
            "event_id": event.event_id
        })

    def _create_qr_code(self, tx_hash: str) -> Image:
        """
        Create a QR code linking to Arc Explorer.

        Args:
            tx_hash: Transaction hash

        Returns:
            ReportLab Image object
        """
        explorer_url = f"https://explorer.arc-testnet.circle.com/tx/{tx_hash}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(explorer_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color=settings.brand_navy, back_color="white")
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return Image(img_buffer, width=40*mm, height=40*mm)

    def _get_styles(self) -> Dict[str, ParagraphStyle]:
        """Get custom paragraph styles for the receipt."""
        return {
            "title": ParagraphStyle(
                'Title',
                fontSize=24,
                leading=30,
                alignment=TA_CENTER,
                textColor=self.brand_navy,
                fontName='Helvetica-Bold',
                spaceAfter=20
            ),
            "subtitle": ParagraphStyle(
                'Subtitle',
                fontSize=14,
                leading=18,
                alignment=TA_CENTER,
                textColor=self.brand_blue,
                fontName='Helvetica',
                spaceAfter=30
            ),
            "heading": ParagraphStyle(
                'Heading',
                fontSize=12,
                leading=16,
                textColor=self.brand_navy,
                fontName='Helvetica-Bold',
                spaceAfter=10
            ),
            "body": ParagraphStyle(
                'Body',
                fontSize=10,
                leading=14,
                textColor=colors.black,
                fontName='Helvetica'
            ),
            "footer": ParagraphStyle(
                'Footer',
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
                textColor=colors.gray,
                fontName='Helvetica'
            ),
            "success": ParagraphStyle(
                'Success',
                fontSize=14,
                leading=18,
                alignment=TA_CENTER,
                textColor=self.brand_green,
                fontName='Helvetica-Bold',
                spaceBefore=20,
                spaceAfter=20
            )
        }

    async def generate_receipt(
        self,
        transaction_type: str,
        event_data: Dict[str, Any],
        event_id: str
    ) -> Path:
        """
        Generate a PDF receipt for a transaction.

        Args:
            transaction_type: Type of transaction (Deposit, Withdraw, Compound)
            event_data: Data from the transaction event
            event_id: Unique event identifier

        Returns:
            Path to the generated PDF
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"receipt_{transaction_type.lower()}_{timestamp}.pdf"
        filepath = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )

        styles = self._get_styles()
        elements = []

        # Header
        elements.append(Paragraph("USYC Protocol Labs", styles["title"]))
        elements.append(Paragraph("Transaction Receipt", styles["subtitle"]))

        # Success badge
        elements.append(Paragraph("Transaction Successful", styles["success"]))

        # Transaction details table
        tx_hash = event_data.get("tx_hash", "N/A")
        timestamp_str = event_data.get("timestamp", datetime.utcnow().isoformat())

        details_data = [
            ["Transaction Type:", transaction_type],
            ["Transaction ID:", event_id[:16] + "..."],
            ["Timestamp:", timestamp_str],
            ["Tx Hash:", tx_hash[:20] + "..." if len(tx_hash) > 20 else tx_hash],
        ]

        # Add type-specific details
        if transaction_type == "Deposit":
            amount = event_data.get("amount", 0)
            shares = event_data.get("shares_received", 0)
            details_data.extend([
                ["Amount Deposited:", f"{amount:.6f} USDC"],
                ["Shares Received:", f"{shares:.6f}"],
            ])
        elif transaction_type == "Withdraw":
            shares = event_data.get("shares", 0)
            assets = event_data.get("assets_received", 0)
            details_data.extend([
                ["Shares Withdrawn:", f"{shares:.6f}"],
                ["USDC Received:", f"{assets:.6f} USDC"],
            ])
        elif transaction_type == "Compound":
            yield_amount = event_data.get("yield_compounded", "Auto")
            details_data.extend([
                ["Yield Compounded:", str(yield_amount)],
            ])

        # Demo mode indicator
        if event_data.get("demo"):
            details_data.append(["Mode:", "Demo (Simulated)"])

        table = Table(details_data, colWidths=[60*mm, 100*mm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.brand_navy),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20*mm))

        # QR Code section
        if tx_hash and tx_hash != "N/A" and not tx_hash.startswith("0xdemo"):
            elements.append(Paragraph("Scan to view on Arc Explorer:", styles["heading"]))
            qr_image = self._create_qr_code(tx_hash)
            elements.append(qr_image)
        else:
            elements.append(Paragraph("View on Arc Explorer", styles["heading"]))
            elements.append(Paragraph(
                "https://explorer.arc-testnet.circle.com",
                styles["body"]
            ))

        elements.append(Spacer(1, 30*mm))

        # Footer
        elements.append(Paragraph(
            "Vault Contract: " + settings.vault_contract,
            styles["footer"]
        ))
        elements.append(Paragraph(
            "Network: Arc Testnet | Generated by USYC Protocol Labs",
            styles["footer"]
        ))
        elements.append(Paragraph(
            f"Receipt generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            styles["footer"]
        ))

        doc.build(elements)

        print(f"[{self.name}] Receipt generated: {filepath}")
        return filepath

    def list_receipts(self) -> list:
        """List all generated receipts."""
        return sorted(self.output_dir.glob("receipt_*.pdf"), reverse=True)
