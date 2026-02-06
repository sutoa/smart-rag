#!/usr/bin/env python3
"""Create sample PDF fixtures for testing.

Run this script to generate test PDFs:
    python tests/fixtures/sample_pdfs/create_fixtures.py

Requires: pip install reportlab
"""

import os
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
except ImportError:
    print("Please install reportlab: pip install reportlab")
    exit(1)

OUTPUT_DIR = Path(__file__).parent


def create_employee_handbook():
    """Create a sample employee handbook PDF."""
    filename = OUTPUT_DIR / "employee_handbook.pdf"
    doc = SimpleDocTemplate(str(filename), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
    )
    story.append(Paragraph("Employee Handbook", title_style))
    story.append(Spacer(1, 12))

    # Section 1: Introduction
    story.append(Paragraph("1. Introduction", styles['Heading2']))
    story.append(Paragraph(
        "Welcome to Acme Corporation. This handbook provides essential information "
        "about our company policies, procedures, and expectations. All employees are "
        "expected to read and understand this document.",
        styles['Normal']
    ))
    story.append(Spacer(1, 12))

    # Section 2: Roles
    story.append(Paragraph("2. Key Roles and Definitions", styles['Heading2']))
    story.append(Paragraph(
        "<b>Client Senior Manager (CSM)</b>: A Client Senior Manager is defined as a "
        "senior-level professional responsible for managing key client relationships "
        "and ensuring successful delivery of services. CSMs serve as the primary point "
        "of contact for strategic clients and are accountable for client satisfaction "
        "and retention.",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Project Lead (PL)</b>: A Project Lead oversees the day-to-day execution of "
        "projects, coordinates team members, and reports progress to stakeholders.",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Technical Architect (TA)</b>: A Technical Architect designs system "
        "architecture, makes technology decisions, and ensures technical quality "
        "across projects.",
        styles['Normal']
    ))
    story.append(Spacer(1, 12))

    # Section 3: Policies
    story.append(Paragraph("3. Company Policies", styles['Heading2']))
    story.append(Paragraph(
        "All employees must adhere to the following policies:",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))

    policies = [
        "Remote work is permitted with manager approval",
        "Annual leave is 20 days per year",
        "Sick leave requires a doctor's note after 3 consecutive days",
        "Performance reviews occur quarterly",
    ]
    for policy in policies:
        story.append(Paragraph(f"• {policy}", styles['Normal']))

    story.append(Spacer(1, 12))

    # Section 4: Table
    story.append(Paragraph("4. Leave Entitlements", styles['Heading2']))

    table_data = [
        ['Leave Type', 'Days/Year', 'Carryover'],
        ['Annual Leave', '20', 'Up to 5 days'],
        ['Sick Leave', '10', 'No carryover'],
        ['Parental Leave', '12 weeks', 'N/A'],
        ['Bereavement', '5', 'N/A'],
    ]
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)

    doc.build(story)
    print(f"Created: {filename}")


def create_technical_guide():
    """Create a sample technical guide PDF."""
    filename = OUTPUT_DIR / "technical_guide.pdf"
    doc = SimpleDocTemplate(str(filename), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("Technical Architecture Guide", styles['Heading1']))
    story.append(Spacer(1, 12))

    # Section 1
    story.append(Paragraph("1. System Overview", styles['Heading2']))
    story.append(Paragraph(
        "Our system uses a microservices architecture with the following components:",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))

    components = [
        "API Gateway: Handles authentication and request routing",
        "User Service: Manages user accounts and profiles",
        "Order Service: Processes orders and payments",
        "Notification Service: Sends emails and push notifications",
    ]
    for comp in components:
        story.append(Paragraph(f"• {comp}", styles['Normal']))

    story.append(Spacer(1, 12))

    # Section 2
    story.append(Paragraph("2. Database Schema", styles['Heading2']))
    story.append(Paragraph(
        "The primary database is PostgreSQL with the following key tables:",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))

    db_table = [
        ['Table', 'Description', 'Primary Key'],
        ['users', 'User accounts', 'user_id'],
        ['orders', 'Customer orders', 'order_id'],
        ['products', 'Product catalog', 'product_id'],
        ['audit_log', 'System events', 'log_id'],
    ]
    table = Table(db_table)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
    ]))
    story.append(table)

    story.append(Spacer(1, 12))

    # Section 3
    story.append(Paragraph("3. API Endpoints", styles['Heading2']))
    story.append(Paragraph(
        "All API endpoints require authentication via JWT tokens. "
        "The base URL is https://api.example.com/v1/",
        styles['Normal']
    ))

    doc.build(story)
    print(f"Created: {filename}")


def create_company_policies():
    """Create a sample company policies PDF."""
    filename = OUTPUT_DIR / "company_policies.pdf"
    doc = SimpleDocTemplate(str(filename), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("Company Policies 2026", styles['Heading1']))
    story.append(Spacer(1, 12))

    # Security Policy
    story.append(Paragraph("Security Policy", styles['Heading2']))
    story.append(Paragraph(
        "All employees must follow these security guidelines:",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))

    security_rules = [
        "Use strong passwords with at least 12 characters",
        "Enable two-factor authentication on all accounts",
        "Never share login credentials with others",
        "Report suspicious emails to security@company.com",
        "Lock your computer when away from your desk",
    ]
    for rule in security_rules:
        story.append(Paragraph(f"• {rule}", styles['Normal']))

    story.append(Spacer(1, 12))

    # Data Privacy
    story.append(Paragraph("Data Privacy Policy", styles['Heading2']))
    story.append(Paragraph(
        "Customer data must be handled according to GDPR regulations. "
        "Personal information should only be accessed when necessary for "
        "job duties. Data retention period is 7 years for financial records "
        "and 3 years for general correspondence.",
        styles['Normal']
    ))

    story.append(Spacer(1, 12))

    # Travel Policy
    story.append(Paragraph("Travel and Expense Policy", styles['Heading2']))
    story.append(Paragraph(
        "Business travel must be pre-approved by your manager. "
        "Expense reports should be submitted within 30 days of travel. "
        "Maximum per diem rates are listed in the table below.",
        styles['Normal']
    ))
    story.append(Spacer(1, 6))

    expense_table = [
        ['City Category', 'Hotel/Night', 'Meals/Day'],
        ['Tier 1 (NYC, SF, London)', '$350', '$100'],
        ['Tier 2 (Chicago, Boston)', '$250', '$75'],
        ['Tier 3 (Other)', '$150', '$50'],
    ]
    table = Table(expense_table)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)

    doc.build(story)
    print(f"Created: {filename}")


if __name__ == "__main__":
    print(f"Creating sample PDFs in: {OUTPUT_DIR}")
    create_employee_handbook()
    create_technical_guide()
    create_company_policies()
    print("\nDone! Sample PDFs created for testing.")
