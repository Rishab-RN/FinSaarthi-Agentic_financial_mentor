"""
FinSaarthi — Financial PDF Parser
=================================
Handles extractive parsing of CAMS Consolidated Account Statements (CAS) 
and Form 16 (Income Tax) documents.

File: tools/pdf_parser.py
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import pdfplumber
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf_parser")


class CAMSParser:
    """
    Parser for CAMS-generated Consolidated Account Statements (CAS).
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.full_text = ""
        self._load_text()

    def _load_text(self):
        """Load text from PDF using pdfplumber with PyMuPDF fallback."""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    self.full_text += (page.extract_text() or "") + "\n"
        except Exception as e:
            logger.warning(f"pdfplumber failed, falling back to PyMuPDF: {e}")
            doc = fitz.open(self.pdf_path)
            for page in doc:
                self.full_text += page.get_text() + "\n"

    def extract_all_transactions(self) -> pd.DataFrame:
        """
        Extract all transaction rows from the statement.
        Format: Date | Description | Amount | Units | NAV | Balance
        """
        transactions = []
        # Regex for CAMS transaction rows: DD-MMM-YYYY followed by description and numbers
        # Example: 01-Jan-2024 SIP Purchase - Mirae Asset... 5000.00 50.123 99.75 1250.456
        pattern = re.compile(
            r"(\d{2}-[a-zA-Z]{3}-\d{4})\s+(.*?)\s+([-+]?[\d,]+\.\d{2,})\s+([-+]?[\d,]+\.\d{3,})\s+([\d,]+\.\d{2,})\s+([\d,]+\.\d{3,})"
        )

        current_fund = "Unknown Fund"
        lines = self.full_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Detect Fund Name (Usually uppercase or starts with specific house names)
            if any(house in line.upper() for house in ["MIRAE", "PARAG", "HDFC", "SBI", "AXIS", "ICICI"]):
                if "TOTAL" not in line.upper() and len(line) > 10:
                    current_fund = line
            
            match = pattern.search(line)
            if match:
                date_str, desc, amount, units, nav, balance = match.groups()
                
                # Determine transaction type
                desc_upper = desc.upper()
                if "SIP" in desc_upper: t_type = "SIP"
                elif "PURCHASE" in desc_upper: t_type = "Purchase"
                elif "REDEMPTION" in desc_upper or "REDEEM" in desc_upper: t_type = "Redemption"
                elif "SWITCH" in desc_upper: t_type = "Switch"
                else: t_type = "Other"

                transactions.append({
                    "date": datetime.strptime(date_str, "%d-%b-%Y"),
                    "fund_name": current_fund,
                    "transaction_type": t_type,
                    "description": desc.strip(),
                    "amount": float(amount.replace(',', '')),
                    "units": float(units.replace(',', '')),
                    "nav": float(nav.replace(',', '')),
                    "balance_units": float(balance.replace(',', ''))
                })

        df = pd.DataFrame(transactions)
        if not df.empty:
            df = df.sort_values('date')
        return df

    def extract_current_holdings(self) -> pd.DataFrame:
        """
        Extract current valuation and summary of holdings.
        """
        holdings = []
        # Pattern for summary rows
        # Example: Mirae Asset Large Cap Fund (Equity) Folio: 12345 Units: 1000.000 NAV: 105.50 Value: 105500.00
        lines = self.full_text.split('\n')
        for line in lines:
            if "Portfolio Summary" in line or "Statement Period" in line: continue
            
            # Simple extractive logic for summary lines
            if "Folio:" in line and "Units:" in line:
                try:
                    fund_name = line.split("Folio:")[0].strip()
                    folio = re.search(r"Folio:\s*(\w+)", line).group(1)
                    units = re.search(r"Units:\s*([\d,]+\.\d+)", line).group(1).replace(',', '')
                    nav = re.search(r"NAV:\s*([\d,]+\.\d+)", line).group(1).replace(',', '')
                    val = re.search(r"Value:\s*([\d,]+\.\d+)", line).group(1).replace(',', '')
                    
                    holdings.append({
                        "fund_name": fund_name,
                        "folio_number": folio,
                        "units": float(units),
                        "current_nav": float(nav),
                        "current_value": float(val),
                        "scheme_type": self.get_fund_category(fund_name)
                    })
                except Exception:
                    continue
        
        return pd.DataFrame(holdings)

    def get_fund_category(self, fund_name: str) -> str:
        """Classify fund category based on its name."""
        name = fund_name.lower()
        if any(kd in name for kd in ["flexi", "multi cap", "large cap", "mid cap", "small cap", "equity", "bluechip"]):
            return "Equity"
        if any(kd in name for kd in ["debt", "liquid", "overnight", "gilt", "treasury", "income"]):
            return "Debt"
        if any(kd in name for kd in ["hybrid", "balanced", "aggressive", "dynamic asset"]):
            return "Hybrid"
        return "Other"

    def prepare_for_xirr(self) -> List[Dict[str, Any]]:
        """
        Format data specifically for tools.financial_calc.calculate_xirr
        Returns: list of {fund_name, cashflows: list, dates: list}
        """
        df = self.extract_all_transactions()
        holdings = self.extract_current_holdings()
        
        prepared = []
        if df.empty: return []

        for fund in df['fund_name'].unique():
            fund_tx = df[df['fund_name'] == fund]
            cashflows = list(fund_tx['amount'] * -1) # Investments are negative
            dates = list(fund_tx['date'].dt.date)
            
            # Add current value as final positive cashflow
            fund_holding = holdings[holdings['fund_name'] == fund]
            if not fund_holding.empty:
                cashflows.append(float(fund_holding.iloc[0]['current_value']))
                dates.append(datetime.now().date())
            
            prepared.append({
                "fund_name": fund,
                "cashflows": cashflows,
                "dates": dates
            })
        return prepared


class Form16Parser:
    """
    Parser for Indian Income Tax Form 16 (specifically Part B).
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.full_text = ""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                self.full_text += (page.extract_text() or "") + "\n"

    def _extract_numeric(self, pattern: str) -> float:
        match = re.search(pattern, self.full_text, re.IGNORECASE | re.DOTALL)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0.0

    def extract_salary_details(self) -> Dict[str, Any]:
        """Extract primary salary components and employer metadata."""
        return {
            "gross_salary": self._extract_numeric(r"Gross Salary.*?(\d+[\d,]*\.\d{2})"),
            "basic_salary": self._extract_numeric(r"Basic Salary.*?(\d+[\d,]*\.\d{2})"),
            "hra_received": self._extract_numeric(r"House Rent Allowance.*?(\d+[\d,]*\.\d{2})"),
            "special_allowance": self._extract_numeric(r"Special Allowance.*?(\d+[\d,]*\.\d{2})"),
            "tds_deducted": self._extract_numeric(r"Tax payable on total income.*?(\d+[\d,]*\.\d{2})"),
            "assessment_year": re.search(r"Assessment Year\s*(\d{4}-\d{2})", self.full_text).group(1) if re.search(r"Assessment Year", self.full_text) else "N/A"
        }

    def extract_deductions_claimed(self) -> Dict[str, Any]:
        """Extract Chapter VI-A deductions and HRA exemptions."""
        return {
            "sec_80c": self._extract_numeric(r"Section 80C.*?(\d+[\d,]*\.\d{2})"),
            "sec_80d": self._extract_numeric(r"Section 80D.*?(\d+[\d,]*\.\d{2})"),
            "hra_exemption": self._extract_numeric(r"exemption under section 10\(13A\).*?(\d+[\d,]*\.\d{2})"),
            "home_loan_interest": self._extract_numeric(r"Interest on self-occupied house.*?(\d+[\d,]*\.\d{2})")
        }


def create_sample_cams_pdf(output_path: str) -> None:
    """
    Generate a realistic dummy CAMS PDF for hackathon demonstration.
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>CAMS Consolidated Account Statement</b>", styles['Title']))
    elements.append(Paragraph(f"Statement Period: 01-Jan-2022 to {datetime.now().strftime('%d-%b-%Y')}", styles['Normal']))
    elements.append(Paragraph("<br/><br/>", styles['Normal']))

    funds = [
        {"name": "Mirae Asset Large Cap Fund", "base_nav": 100.0},
        {"name": "Parag Parikh Flexi Cap Fund", "base_nav": 50.0},
        {"name": "HDFC Mid Cap Opportunities Fund", "base_nav": 120.0}
    ]

    for fund in funds:
        elements.append(Paragraph(f"<b>{fund['name']}</b>", styles['Heading2']))
        data = [["Date", "Description", "Amount", "Units", "NAV", "Balance"]]
        
        current_nav = fund['base_nav']
        current_units = 0.0
        
        for i in range(24):
            # SIP of 5000 every month
            date_str = (datetime(2022, 1, 1) + pd.DateOffset(months=i)).strftime('%d-%b-%Y')
            # Simulated NAV growth (approx 1% monthly -> 12.6% CAGR)
            current_nav *= 1.01
            sip_amount = 5000.00
            units_bought = sip_amount / current_nav
            current_units += units_bought
            
            data.append([
                date_str, "SIP Purchase", 
                f"{sip_amount:.2f}", 
                f"{units_bought:.3f}", 
                f"{current_nav:.2f}", 
                f"{current_units:.3f}"
            ])
        
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        
        # Add Portfolio Summary line for this fund
        fv = current_units * current_nav
        summary_text = f"{fund['name']} Folio: 91029384 Units: {current_units:.3f} NAV: {current_nav:.2f} Value: {fv:.2f}"
        elements.append(Paragraph(summary_text, styles['Normal']))
        elements.append(Paragraph("<br/>", styles['Normal']))

    doc.build(elements)
    logger.info(f"Sample CAMS PDF generated at {output_path}")

if __name__ == "__main__":
    import os
    sample_path = "sample_cams.pdf"
    create_sample_cams_pdf(sample_path)
    
    parser = CAMSParser(sample_path)
    tx_df = parser.extract_all_transactions()
    holdings_df = parser.extract_current_holdings()
    
    print("\n--- Extracted Transactions (Sample) ---")
    print(tx_df.head(10))
    
    print("\n--- Extracted Holdings ---")
    print(holdings_df)
    
    # Cleanup sample
    if os.path.exists(sample_path):
        os.remove(sample_path)
