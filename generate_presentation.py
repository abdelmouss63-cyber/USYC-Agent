#!/usr/bin/env python3
"""
USYC Protocol Labs - Hackathon Presentation Generator
Generates a professional 8-slide PDF presentation
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

# Page size - A4 Landscape (16:9 approximation)
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

# Colors from dashboard theme
DARK_BG = colors.HexColor("#0a0f1a")
DARK_CARD = colors.HexColor("#111827")
ELECTRIC_BLUE = colors.HexColor("#58a6ff")
NEON_GREEN = colors.HexColor("#3fb950")
GOLD = colors.HexColor("#ffd700")
WHITE = colors.HexColor("#ffffff")
LIGHT_GRAY = colors.HexColor("#e6e6e6")
PURPLE = colors.HexColor("#9B59B6")
NAVY = colors.HexColor("#1E3A5F")


def draw_background(c):
    """Draw dark gradient-like background"""
    c.setFillColor(DARK_BG)
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

    # Add subtle gradient effect with rectangles
    for i in range(5):
        alpha = 0.02 * (5 - i)
        c.setFillColor(colors.Color(0.2, 0.4, 0.6, alpha))
        c.rect(0, PAGE_HEIGHT * i / 5, PAGE_WIDTH, PAGE_HEIGHT / 5, fill=True, stroke=False)


def draw_header_line(c):
    """Draw decorative header line"""
    c.setStrokeColor(ELECTRIC_BLUE)
    c.setLineWidth(3)
    c.line(50, PAGE_HEIGHT - 60, PAGE_WIDTH - 50, PAGE_HEIGHT - 60)


def draw_footer(c, slide_num):
    """Draw footer with slide number"""
    c.setFillColor(LIGHT_GRAY)
    c.setFont("Helvetica", 12)
    c.drawString(50, 30, "USYC Protocol Labs")
    c.drawRightString(PAGE_WIDTH - 50, 30, f"{slide_num}/8")

    # Footer line
    c.setStrokeColor(ELECTRIC_BLUE)
    c.setLineWidth(1)
    c.line(50, 50, PAGE_WIDTH - 50, 50)


def draw_title(c, title, subtitle=None, y_offset=0):
    """Draw main title"""
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 120 + y_offset, title)

    if subtitle:
        c.setFillColor(ELECTRIC_BLUE)
        c.setFont("Helvetica", 28)
        c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 160 + y_offset, subtitle)


def draw_bullet_point(c, text, x, y, color=NEON_GREEN, text_color=WHITE, font_size=24):
    """Draw a bullet point with text"""
    # Bullet
    c.setFillColor(color)
    c.circle(x, y + 8, 6, fill=True, stroke=False)

    # Text
    c.setFillColor(text_color)
    c.setFont("Helvetica", font_size)
    c.drawString(x + 20, y, text)


def draw_card(c, x, y, width, height, title, items, icon_color=ELECTRIC_BLUE):
    """Draw a card with title and items"""
    # Card background
    c.setFillColor(DARK_CARD)
    c.roundRect(x, y, width, height, 15, fill=True, stroke=False)

    # Card border
    c.setStrokeColor(icon_color)
    c.setLineWidth(2)
    c.roundRect(x, y, width, height, 15, fill=False, stroke=True)

    # Title
    c.setFillColor(icon_color)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(x + 20, y + height - 35, title)

    # Items
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 16)
    line_height = 25
    for i, item in enumerate(items):
        c.drawString(x + 20, y + height - 70 - (i * line_height), f"• {item}")


def slide_1_title(c):
    """SLIDE 1 - Title Slide"""
    draw_background(c)

    # Main title
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 56)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 200, "USYC Protocol Labs")

    # Subtitle
    c.setFillColor(ELECTRIC_BLUE)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 270, "Multi-Agent DeFi System")

    # Tagline
    c.setFillColor(NEON_GREEN)
    c.setFont("Helvetica", 28)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 340, "AI Agents  x  DeFi  x  Arc Network")

    # Decorative elements
    c.setStrokeColor(ELECTRIC_BLUE)
    c.setLineWidth(3)
    c.line(150, PAGE_HEIGHT - 380, PAGE_WIDTH - 150, PAGE_HEIGHT - 380)

    # Hackathon info
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 440, "Agentic Commerce on Arc Hackathon")

    c.setFillColor(WHITE)
    c.setFont("Helvetica", 20)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 480, "Track: Best Gateway-Based Micropayments Integration")

    # Footer badges
    c.setFillColor(LIGHT_GRAY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_WIDTH / 2, 60, "Circle  |  Arc Network  |  lablab.ai")

    draw_footer(c, 1)


def slide_2_problem(c):
    """SLIDE 2 - The Problem"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "The Problem")

    problems = [
        ("DeFi requires constant human intervention", ELECTRIC_BLUE),
        ("No way for AI agents to pay automatically", NEON_GREEN),
        ("Yield management is manual and error-prone", GOLD),
        ("No audit trails for autonomous transactions", PURPLE),
    ]

    y_start = PAGE_HEIGHT - 220
    for i, (problem, color) in enumerate(problems):
        y = y_start - (i * 80)

        # Problem card
        c.setFillColor(DARK_CARD)
        c.roundRect(100, y - 20, PAGE_WIDTH - 200, 60, 10, fill=True, stroke=False)
        c.setStrokeColor(color)
        c.setLineWidth(3)
        c.roundRect(100, y - 20, PAGE_WIDTH - 200, 60, 10, fill=False, stroke=True)

        # X icon
        c.setFillColor(colors.HexColor("#ff4444"))
        c.setFont("Helvetica-Bold", 28)
        c.drawString(120, y, "X")

        # Problem text
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(170, y, problem)

    draw_footer(c, 2)


def slide_3_solution(c):
    """SLIDE 3 - The Solution"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "The Solution")

    solutions = [
        ("Deposit USDC", "Treasury yields via Teller", ELECTRIC_BLUE),
        ("x402 Protocol", "Auto-pay for APIs", NEON_GREEN),
        ("PDF Receipts", "Complete audit trails", GOLD),
        ("Multi-Agent", "Zero human intervention", PURPLE),
    ]

    card_width = 180
    card_height = 200
    start_x = 80
    gap = (PAGE_WIDTH - 2 * start_x - 4 * card_width) / 3
    y = PAGE_HEIGHT - 450

    for i, (title, desc, color) in enumerate(solutions):
        x = start_x + i * (card_width + gap)

        # Card
        c.setFillColor(DARK_CARD)
        c.roundRect(x, y, card_width, card_height, 15, fill=True, stroke=False)
        c.setStrokeColor(color)
        c.setLineWidth(3)
        c.roundRect(x, y, card_width, card_height, 15, fill=False, stroke=True)

        # Icon circle
        c.setFillColor(color)
        c.circle(x + card_width/2, y + card_height - 50, 30, fill=True, stroke=False)

        # Checkmark
        c.setFillColor(DARK_BG)
        c.setFont("Helvetica-Bold", 32)
        c.drawCentredString(x + card_width/2, y + card_height - 62, "✓")

        # Title
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(x + card_width/2, y + card_height - 110, title)

        # Description (wrap text)
        c.setFillColor(LIGHT_GRAY)
        c.setFont("Helvetica", 14)
        words = desc.split()
        if len(words) > 2:
            c.drawCentredString(x + card_width/2, y + card_height - 140, " ".join(words[:2]))
            c.drawCentredString(x + card_width/2, y + card_height - 158, " ".join(words[2:]))
        else:
            c.drawCentredString(x + card_width/2, y + card_height - 140, desc)

    draw_footer(c, 3)


def slide_4_architecture(c):
    """SLIDE 4 - Architecture"""
    draw_background(c)
    draw_header_line(c)
    # Smaller title to avoid cutoff
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 100, "Multi-Agent Architecture")

    agents = [
        ("Vault Agent", "DeFi Operations\nDeposit/Withdraw/Compound", ELECTRIC_BLUE),
        ("Media Agent", "PDF Generation\nReceipt & Reports", NEON_GREEN),
        ("Gateway Client", "Circle Integration\nUSDC Transfers", GOLD),
        ("x402 Handler", "Payment Protocol\nAuto-pay APIs", PURPLE),
    ]

    # Center Y for the agents
    center_y = PAGE_HEIGHT / 2 - 30
    box_width = 170
    box_height = 120

    # Draw central hub
    hub_x = PAGE_WIDTH / 2
    hub_y = center_y
    c.setFillColor(DARK_CARD)
    c.circle(hub_x, hub_y, 50, fill=True, stroke=False)
    c.setStrokeColor(WHITE)
    c.setLineWidth(2)
    c.circle(hub_x, hub_y, 50, fill=False, stroke=True)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(hub_x, hub_y + 5, "Event")
    c.drawCentredString(hub_x, hub_y - 12, "Bus")

    # Agent positions (around the hub)
    positions = [
        (120, center_y + 100),      # Top left
        (PAGE_WIDTH - 290, center_y + 100),  # Top right
        (120, center_y - 150),      # Bottom left
        (PAGE_WIDTH - 290, center_y - 150),  # Bottom right
    ]

    for i, ((name, desc, color), (x, y)) in enumerate(zip(agents, positions)):
        # Connection line to hub
        c.setStrokeColor(color)
        c.setLineWidth(2)
        box_center_x = x + box_width / 2
        box_center_y = y + box_height / 2
        c.line(box_center_x, box_center_y, hub_x, hub_y)

        # Agent box
        c.setFillColor(DARK_CARD)
        c.roundRect(x, y, box_width, box_height, 12, fill=True, stroke=False)
        c.setStrokeColor(color)
        c.setLineWidth(3)
        c.roundRect(x, y, box_width, box_height, 12, fill=False, stroke=True)

        # Agent name
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(x + box_width/2, y + box_height - 30, name)

        # Description
        c.setFillColor(LIGHT_GRAY)
        c.setFont("Helvetica", 12)
        lines = desc.split('\n')
        for j, line in enumerate(lines):
            c.drawCentredString(x + box_width/2, y + box_height - 55 - j*16, line)

    draw_footer(c, 4)


def slide_5_tech_stack(c):
    """SLIDE 5 - Tech Stack"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "Technology Stack")

    stacks = [
        ("Backend", ["Python 3.11+", "FastAPI", "Web3.py", "ReportLab"], ELECTRIC_BLUE),
        ("Smart Contracts", ["Solidity 0.8.x", "UUPS Proxy", "OpenZeppelin", "ERC-4626"], NEON_GREEN),
        ("Circle Integration", ["Gateway API", "Smart Wallets", "x402 Protocol", "CCTP"], GOLD),
    ]

    card_width = 240
    card_height = 280
    start_x = (PAGE_WIDTH - 3 * card_width - 2 * 40) / 2
    y = PAGE_HEIGHT - 480

    for i, (title, items, color) in enumerate(stacks):
        x = start_x + i * (card_width + 40)

        # Card
        c.setFillColor(DARK_CARD)
        c.roundRect(x, y, card_width, card_height, 15, fill=True, stroke=False)
        c.setStrokeColor(color)
        c.setLineWidth(3)
        c.roundRect(x, y, card_width, card_height, 15, fill=False, stroke=True)

        # Title bar
        c.setFillColor(color)
        c.roundRect(x, y + card_height - 50, card_width, 50, 15, fill=True, stroke=False)
        c.rect(x, y + card_height - 50, card_width, 15, fill=True, stroke=False)

        # Title text
        c.setFillColor(DARK_BG)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(x + card_width/2, y + card_height - 35, title)

        # Items
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 18)
        for j, item in enumerate(items):
            c.drawCentredString(x + card_width/2, y + card_height - 90 - j*45, item)

    draw_footer(c, 5)


def slide_6_features(c):
    """SLIDE 6 - Key Features"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "Key Features")

    features = [
        ("Autonomous x402 Payments", ELECTRIC_BLUE),
        ("Real-time Dashboard", NEON_GREEN),
        ("Multi-Agent Orchestration", GOLD),
        ("PDF Receipt Generation", PURPLE),
        ("Circle Gateway Integration", ELECTRIC_BLUE),
    ]

    y_start = PAGE_HEIGHT - 220

    for i, (feature, color) in enumerate(features):
        y = y_start - (i * 55)  # Reduced spacing

        # Feature row (narrower to make room for badge on right)
        c.setFillColor(DARK_CARD)
        c.roundRect(100, y - 12, PAGE_WIDTH - 450, 45, 10, fill=True, stroke=False)

        # Colored left bar
        c.setFillColor(color)
        c.roundRect(100, y - 12, 6, 45, 3, fill=True, stroke=False)

        # Checkmark
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(120, y, "✓")

        # Feature text
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(155, y, feature)

    # Circle Whitelisted badge - positioned on the right side
    badge_x = PAGE_WIDTH - 280
    badge_y = PAGE_HEIGHT / 2 - 30
    badge_width = 230
    badge_height = 70
    c.setFillColor(NEON_GREEN)
    c.roundRect(badge_x, badge_y, badge_width, badge_height, 15, fill=True, stroke=False)
    c.setFillColor(DARK_BG)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(badge_x + badge_width/2, badge_y + 42, "CIRCLE")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(badge_x + badge_width/2, badge_y + 18, "WHITELISTED ✓")

    draw_footer(c, 6)


def slide_7_deployed(c):
    """SLIDE 7 - Deployed Infrastructure"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "Deployed Infrastructure")

    # Contract address card
    card_y = PAGE_HEIGHT - 280
    c.setFillColor(DARK_CARD)
    c.roundRect(80, card_y, PAGE_WIDTH - 160, 100, 15, fill=True, stroke=False)
    c.setStrokeColor(ELECTRIC_BLUE)
    c.setLineWidth(2)
    c.roundRect(80, card_y, PAGE_WIDTH - 160, 100, 15, fill=False, stroke=True)

    c.setFillColor(ELECTRIC_BLUE)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, card_y + 65, "Smart Contract:")

    c.setFillColor(NEON_GREEN)
    c.setFont("Courier-Bold", 18)
    c.drawString(100, card_y + 30, "0x2f685b5Ef138Ac54F4CB1155A9C5922c5A58eD25")

    # Info grid
    info = [
        ("Network", "Arc Testnet", ELECTRIC_BLUE),
        ("Status", "Circle Whitelisted", NEON_GREEN),
        ("Domain", "usyc-protocols.tech", GOLD),
        ("Achievement", "First on Arc Testnet", PURPLE),
    ]

    card_width = 180
    card_height = 110
    start_x = 80
    gap = (PAGE_WIDTH - 2 * start_x - 4 * card_width) / 3
    y = PAGE_HEIGHT - 470

    for i, (label, value, color) in enumerate(info):
        x = start_x + i * (card_width + gap)

        # Card
        c.setFillColor(DARK_CARD)
        c.roundRect(x, y, card_width, card_height, 12, fill=True, stroke=False)
        c.setStrokeColor(color)
        c.setLineWidth(2)
        c.roundRect(x, y, card_width, card_height, 12, fill=False, stroke=True)

        # Label
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(x + card_width/2, y + card_height - 30, label)

        # Value
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 14)
        # Handle long text
        if len(value) > 18:
            words = value.split()
            c.drawCentredString(x + card_width/2, y + card_height - 60, " ".join(words[:2]))
            if len(words) > 2:
                c.drawCentredString(x + card_width/2, y + card_height - 78, " ".join(words[2:]))
        else:
            c.drawCentredString(x + card_width/2, y + card_height - 65, value)

    draw_footer(c, 7)


def slide_8_contact(c):
    """SLIDE 8 - Contact"""
    draw_background(c)
    draw_header_line(c)
    draw_title(c, "Contact & Links")

    contacts = [
        ("Email", "contact@usyc-protocols.tech", ELECTRIC_BLUE),
        ("Personal", "abdelmouss63@gmail.com", NEON_GREEN),
        ("Twitter", "@USYCProtocol", GOLD),
        ("Twitter", "@mous68881", PURPLE),
    ]

    y_start = PAGE_HEIGHT - 240

    for i, (label, value, color) in enumerate(contacts):
        y = y_start - (i * 60)

        # Contact row
        c.setFillColor(DARK_CARD)
        c.roundRect(200, y - 10, PAGE_WIDTH - 400, 45, 10, fill=True, stroke=False)

        # Colored accent
        c.setFillColor(color)
        c.circle(230, y + 12, 12, fill=True, stroke=False)

        # Label
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(260, y + 5, f"{label}:")

        # Value
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 18)
        c.drawString(380, y + 5, value)

    # Track badge - wider and smaller font to fit text
    badge_y = 90
    badge_width = 520
    c.setFillColor(GOLD)
    c.roundRect(PAGE_WIDTH/2 - badge_width/2, badge_y, badge_width, 55, 27, fill=True, stroke=False)
    c.setFillColor(DARK_BG)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_WIDTH/2, badge_y + 32, "Track:")
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(PAGE_WIDTH/2, badge_y + 12, "Best Gateway-Based Micropayments Integration")

    # Thank you
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PAGE_WIDTH/2, 55, "Thank You!")

    draw_footer(c, 8)


def generate_presentation():
    """Generate the full presentation PDF"""
    output_path = os.path.join(os.path.dirname(__file__), "USYC_Protocol_Labs_Presentation.pdf")

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setTitle("USYC Protocol Labs - Hackathon Presentation")
    c.setAuthor("USYC Protocol Labs")
    c.setSubject("Agentic Commerce on Arc Hackathon")

    # Generate all slides
    slides = [
        slide_1_title,
        slide_2_problem,
        slide_3_solution,
        slide_4_architecture,
        slide_5_tech_stack,
        slide_6_features,
        slide_7_deployed,
        slide_8_contact,
    ]

    for i, slide_func in enumerate(slides):
        slide_func(c)
        if i < len(slides) - 1:
            c.showPage()

    c.save()
    print(f"Presentation generated: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_presentation()
