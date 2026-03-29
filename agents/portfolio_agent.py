"""
FinSaarthi — Portfolio X-Ray Agent (Module 1)
===============================================
The showstopper demo feature. This agent receives a CAMS Consolidated
Account Statement PDF, runs complete mutual fund portfolio analysis, and
returns structured results ready for Streamlit rendering.

Architecture:
    ┌────────────┐     ┌──────────────┐     ┌──────────────────┐
    │  CAMS PDF  │ ──▶ │ PDF Parser   │ ──▶ │ PortfolioAgent   │
    └────────────┘     │ (teammate's  │     │ _parse_portfolio  │
                       │  tools/)     │     │ _compute_xirr     │
                       └──────────────┘     │ _compute_overlap  │
                                            │ _expense_analysis │
                                            │ _benchmark        │
                                            │ _rebalancing (LLM)│
                                            └──────────────────┘

    Rule: ALL numbers computed in Python. LLM ONLY generates natural
    language explanations of pre-computed results.

File: agents/portfolio_agent.py
Branch: feature/agents
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ── Foundation imports (from main branch) ─────────────────────────────────────
from state import FinSaarthiState, PortfolioData
from tools.audit_logger import AuditLogger

# ── Teammate imports (will be available after merge) ──────────────────────────
# These modules live on separate branches. The agent is designed to gracefully
# degrade if they aren't present yet, using built-in fallback implementations.
try:
    from tools.financial_calc import (
        calculate_xirr,
        calculate_portfolio_overlap,
        calculate_expense_drag,
    )
    _HAS_FINANCIAL_CALC = True
except ImportError:
    _HAS_FINANCIAL_CALC = False

try:
    from tools.pdf_parser import CAMSParser
    _HAS_PDF_PARSER = True
except ImportError:
    _HAS_PDF_PARSER = False

try:
    from rag.knowledge_base import FinancialKnowledgeBase
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger("finsaarthi.portfolio_agent")

# ==============================================================================
# REFERENCE DATA: Top Indian MF Holdings (for overlap & expense analysis)
# ==============================================================================

FUND_HOLDINGS_DATABASE: Dict[str, List[str]] = {
    # Large Cap
    "Mirae Asset Large Cap Fund": [
        "HDFC Bank", "ICICI Bank", "Infosys", "TCS", "Reliance Industries",
        "Axis Bank", "Kotak Mahindra Bank", "L&T", "SBI", "Bharti Airtel",
    ],
    "SBI BlueChip Fund": [
        "HDFC Bank", "ICICI Bank", "Infosys", "Bharti Airtel", "TCS",
        "Reliance Industries", "L&T", "HCL Technologies", "SBI", "ITC",
    ],
    "Axis BlueChip Fund": [
        "HDFC Bank", "Bajaj Finance", "TCS", "Infosys", "Avenue Supermarts",
        "Kotak Mahindra Bank", "Hindustan Unilever", "Titan Company", "ICICI Bank", "Nestle India",
    ],
    # Flexi Cap
    "Parag Parikh Flexi Cap Fund": [
        "HDFC Bank", "Coal India", "ITC", "Power Grid Corp", "Alphabet Inc",
        "Microsoft Corp", "Meta Platforms", "Bajaj Holdings", "Motilal Oswal", "HCL Technologies",
    ],
    "HDFC Flexi Cap Fund": [
        "ICICI Bank", "HDFC Bank", "SBI", "Axis Bank", "Cipla",
        "Bharti Airtel", "HCL Technologies", "Coal India", "Infosys", "NTPC",
    ],
    # Mid Cap
    "HDFC Mid Cap Opportunities Fund": [
        "Persistent Systems", "Coforge", "Dixon Technologies", "Voltas", "Ashok Leyland",
        "Tube Investments", "Cummins India", "Sona BLW Precision", "BSE Ltd", "KPIT Technologies",
    ],
    "Kotak Emerging Equity Fund": [
        "Persistent Systems", "Supreme Industries", "Coforge", "Voltas", "Tube Investments",
        "Schaeffler India", "Sundaram Finance", "CG Power", "The Phoenix Mills", "Thermax",
    ],
    # Small Cap
    "Axis Small Cap Fund": [
        "Garware Technical", "Birla Corporation", "Cera Sanitaryware", "Jamna Auto",
        "Finolex Cables", "NOCIL", "Balaji Amines", "Vinati Organics",
        "Intellect Design Arena", "Mastek",
    ],
    "Nippon India Small Cap Fund": [
        "KPIT Technologies", "Tube Investments", "Karur Vysya Bank", "Persistent Systems",
        "Multi Commodity Exchange", "Radico Khaitan", "Ratnamani Metals", "CG Power",
        "Navin Fluorine", "Blue Star",
    ],
    # Index
    "UTI Nifty 50 Index Fund": [
        "HDFC Bank", "Reliance Industries", "ICICI Bank", "Infosys", "TCS",
        "Bharti Airtel", "ITC", "SBI", "L&T", "Kotak Mahindra Bank",
    ],
}

# Expense ratios for common funds (annual %, direct plan)
FUND_EXPENSE_RATIOS: Dict[str, float] = {
    "Mirae Asset Large Cap Fund": 0.53,
    "SBI BlueChip Fund": 0.79,
    "Axis BlueChip Fund": 0.49,
    "Parag Parikh Flexi Cap Fund": 0.63,
    "HDFC Flexi Cap Fund": 0.75,
    "HDFC Mid Cap Opportunities Fund": 0.80,
    "Kotak Emerging Equity Fund": 0.42,
    "Axis Small Cap Fund": 0.52,
    "Nippon India Small Cap Fund": 0.68,
    "UTI Nifty 50 Index Fund": 0.18,
}

# Benchmark returns (annualized 5-year as of Mar 2026, approximate)
BENCHMARK_RETURNS: Dict[str, float] = {
    "Nifty 50": 0.132,
    "Nifty Midcap 150": 0.158,
    "Nifty Smallcap 250": 0.161,
    "Category Avg (Equity)": 0.124,
    "Fixed Deposit (SBI)": 0.065,
    "Inflation (CPI)": 0.055,
}


# ==============================================================================
# FALLBACK IMPLEMENTATIONS (used when teammate modules not yet merged)
# ==============================================================================

def _fallback_xirr(cashflows: List[float], dates: List[date]) -> float:
    """
    Simple annualized return approximation when scipy-based XIRR
    is not available. Uses basic CAGR formula as fallback.

    Parameters:
        cashflows (List[float]): Cash flow amounts (negative = outflow).
        dates (List[date]): Corresponding dates.

    Returns:
        float: Approximate annualized return as decimal.
    """
    if len(cashflows) < 2 or len(dates) < 2:
        return 0.0

    total_invested = abs(sum(cf for cf in cashflows if cf < 0))
    final_value = sum(cf for cf in cashflows if cf > 0)

    if total_invested <= 0:
        return 0.0

    years = max((max(dates) - min(dates)).days / 365.25, 0.01)
    cagr = (final_value / total_invested) ** (1 / years) - 1
    return round(cagr, 4)


def _fallback_overlap(fund_holdings: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Jaccard similarity overlap calculation — standalone fallback
    when tools/financial_calc.py is not merged yet.

    Parameters:
        fund_holdings (Dict[str, List[str]]): Fund name → list of stock names.

    Returns:
        Dict: overlap_matrix, highest_overlap_pair, recommendation.
    """
    funds = list(fund_holdings.keys())
    matrix: Dict[str, Dict[str, float]] = {}
    highest_overlap = 0.0
    highest_pair = ("", "")

    for i, f1 in enumerate(funds):
        matrix[f1] = {}
        set1 = {s.strip().upper() for s in fund_holdings[f1]}
        for j, f2 in enumerate(funds):
            if i == j:
                matrix[f1][f2] = 1.0
                continue
            set2 = {s.strip().upper() for s in fund_holdings[f2]}
            union = len(set1 | set2)
            overlap = len(set1 & set2) / union if union > 0 else 0.0
            matrix[f1][f2] = round(overlap, 4)

            if i < j and overlap > highest_overlap:
                highest_overlap = overlap
                highest_pair = (f1, f2)

    recommendation = "Healthy diversification across your portfolio."
    if highest_overlap > 0.40:
        recommendation = (
            f"⚠️ High overlap detected: {highest_pair[0]} and {highest_pair[1]} "
            f"share {highest_overlap * 100:.1f}% of their holdings. "
            f"Consider consolidating into one fund to reduce redundancy."
        )
    elif highest_overlap > 0.25:
        recommendation = (
            f"Moderate overlap between {highest_pair[0]} and {highest_pair[1]} "
            f"({highest_overlap * 100:.1f}%). Monitor but not urgent."
        )

    return {
        "overlap_matrix": matrix,
        "highest_overlap_pair": highest_pair,
        "highest_overlap_pct": round(highest_overlap, 4),
        "recommendation": recommendation,
    }


def _fallback_expense_drag(
    portfolio: List[Dict[str, Any]], years: int = 10
) -> Dict[str, Any]:
    """
    Expense ratio drag calculator — standalone fallback.

    Parameters:
        portfolio (List[Dict]): Each item has fund_name, current_value, expense_ratio.
        years (int): Projection period in years.

    Returns:
        Dict: annual_fees_total, ten_year_drag, worst_fund, best_alternative_saving.
    """
    gross_return = 0.12  # Assumed 12% gross market return
    annual_fees = 0.0
    fv_actual = 0.0
    fv_ideal = 0.0
    worst_fund = ""
    highest_er = 0.0

    for item in portfolio:
        val = item.get("current_value", 0)
        er = item.get("expense_ratio", 0) / 100.0  # 1.5% → 0.015
        annual_fees += val * er
        fv_ideal += val * ((1 + gross_return) ** years)
        fv_actual += val * ((1 + (gross_return - er)) ** years)

        if er > highest_er:
            highest_er = er
            worst_fund = item.get("fund_name", "Unknown")

    drag = fv_ideal - fv_actual

    return {
        "annual_fees_total": round(annual_fees, 0),
        "ten_year_drag": round(drag, 0),
        "worst_fund": worst_fund,
        "best_alternative_saving": round(drag * 0.8, 0),
    }


# ==============================================================================
# CAMS PDF FALLBACK PARSER (used when tools/pdf_parser.py not yet merged)
# ==============================================================================

def _fallback_parse_cams(pdf_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate realistic demo data when the PDF parser module isn't available.
    In production, CAMSParser from tools/pdf_parser.py handles actual extraction.

    Parameters:
        pdf_path (str): Path to the CAMS PDF (used for logging only in fallback).

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (transactions_df, holdings_df)
    """
    logger.warning(
        "PDF parser not available. Using demo data for portfolio analysis. "
        "Merge the tools branch to enable actual PDF parsing."
    )

    # Demo transactions (realistic SIP history)
    transactions_data = [
        {"fund_name": "Mirae Asset Large Cap Fund", "date": date(2022, 1, 15), "amount": -10000, "units": 12.5, "nav": 80.0, "type": "SIP"},
        {"fund_name": "Mirae Asset Large Cap Fund", "date": date(2022, 7, 15), "amount": -10000, "units": 11.8, "nav": 84.7, "type": "SIP"},
        {"fund_name": "Mirae Asset Large Cap Fund", "date": date(2023, 1, 15), "amount": -10000, "units": 11.2, "nav": 89.3, "type": "SIP"},
        {"fund_name": "Mirae Asset Large Cap Fund", "date": date(2023, 7, 15), "amount": -10000, "units": 10.5, "nav": 95.2, "type": "SIP"},
        {"fund_name": "Mirae Asset Large Cap Fund", "date": date(2024, 1, 15), "amount": -10000, "units": 9.8, "nav": 102.0, "type": "SIP"},
        {"fund_name": "Parag Parikh Flexi Cap Fund", "date": date(2022, 3, 10), "amount": -15000, "units": 20.0, "nav": 75.0, "type": "SIP"},
        {"fund_name": "Parag Parikh Flexi Cap Fund", "date": date(2022, 9, 10), "amount": -15000, "units": 18.5, "nav": 81.1, "type": "SIP"},
        {"fund_name": "Parag Parikh Flexi Cap Fund", "date": date(2023, 3, 10), "amount": -15000, "units": 17.1, "nav": 87.7, "type": "SIP"},
        {"fund_name": "Parag Parikh Flexi Cap Fund", "date": date(2023, 9, 10), "amount": -15000, "units": 16.3, "nav": 92.0, "type": "SIP"},
        {"fund_name": "HDFC Mid Cap Opportunities Fund", "date": date(2023, 1, 5), "amount": -25000, "units": 15.0, "nav": 166.7, "type": "Lumpsum"},
        {"fund_name": "HDFC Mid Cap Opportunities Fund", "date": date(2023, 6, 5), "amount": -10000, "units": 5.5, "nav": 181.8, "type": "SIP"},
        {"fund_name": "Axis Small Cap Fund", "date": date(2023, 4, 1), "amount": -5000, "units": 6.2, "nav": 80.6, "type": "SIP"},
        {"fund_name": "Axis Small Cap Fund", "date": date(2023, 10, 1), "amount": -5000, "units": 5.8, "nav": 86.2, "type": "SIP"},
        {"fund_name": "Axis Small Cap Fund", "date": date(2024, 4, 1), "amount": -5000, "units": 5.1, "nav": 98.0, "type": "SIP"},
    ]

    # Demo current holdings (as of today)
    holdings_data = [
        {"fund_name": "Mirae Asset Large Cap Fund", "units": 55.8, "nav": 112.5, "current_value": 55.8 * 112.5, "invested_value": 50000, "category": "Large Cap"},
        {"fund_name": "Parag Parikh Flexi Cap Fund", "units": 71.9, "nav": 101.3, "current_value": 71.9 * 101.3, "invested_value": 60000, "category": "Flexi Cap"},
        {"fund_name": "HDFC Mid Cap Opportunities Fund", "units": 20.5, "nav": 215.6, "current_value": 20.5 * 215.6, "invested_value": 35000, "category": "Mid Cap"},
        {"fund_name": "Axis Small Cap Fund", "units": 17.1, "nav": 108.4, "current_value": 17.1 * 108.4, "invested_value": 15000, "category": "Small Cap"},
    ]

    transactions_df = pd.DataFrame(transactions_data)
    holdings_df = pd.DataFrame(holdings_data)

    return transactions_df, holdings_df


# ==============================================================================
# PORTFOLIO AGENT
# ==============================================================================

class PortfolioAgent:
    """
    Module 1: MF Portfolio X-Ray Agent.

    Orchestrates full mutual fund portfolio analysis from a CAMS PDF:
        1. Parse PDF → transactions & holdings DataFrames
        2. Compute per-fund XIRR (annualized returns)
        3. Compute portfolio-level XIRR
        4. Detect fund overlap using Jaccard similarity
        5. Calculate expense ratio drag
        6. Benchmark comparison (vs Nifty 50, Midcap, etc.)
        7. Generate LLM-powered rebalancing recommendations

    All numbers are computed in Python. The LLM is ONLY used at step 7
    to convert pre-computed data into natural language advice.

    Parameters:
        llm: Langchain-compatible LLM instance (Gemini 1.5 Pro).
        knowledge_base: RAG knowledge base for SEBI rules retrieval.
        audit_logger (AuditLogger): SQLite audit trail logger.
    """

    AGENT_NAME: str = "portfolio_agent"

    def __init__(
        self,
        llm: Any,
        knowledge_base: Any = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        """
        Initialize the Portfolio Agent.

        Parameters:
            llm: LangChain-compatible LLM (e.g., ChatGoogleGenerativeAI).
            knowledge_base: FinancialKnowledgeBase instance for RAG queries.
            audit_logger (AuditLogger, optional): Audit logger. Creates one if not given.
        """
        self.llm = llm
        self.knowledge_base = knowledge_base
        self.audit_logger = audit_logger or AuditLogger()

        logger.info("PortfolioAgent initialized.")

    # ── Main Entry Point ──────────────────────────────────────────────────

    def analyze(
        self,
        cams_pdf_path: str,
        risk_profile: str = "moderate",
    ) -> Dict[str, Any]:
        """
        Run full portfolio analysis pipeline on a CAMS PDF.

        This is the main entry point called by the orchestrator or Streamlit UI.
        Every sub-step is individually logged to the audit trail for judge review.

        Parameters:
            cams_pdf_path (str): Filesystem path to the uploaded CAMS PDF.
            risk_profile (str): User's risk tolerance — "conservative", "moderate", or "aggressive".

        Returns:
            Dict[str, Any]: Complete analysis results with keys:
                - portfolio_summary: total invested, current value, overall XIRR
                - xirr_by_fund: per-fund performance data
                - portfolio_xirr: overall portfolio XIRR
                - overlap_analysis: overlap matrix and recommendations
                - expense_analysis: fee drag impact
                - benchmark_comparison: alpha/beta vs indices
                - rebalancing_plan: LLM-generated advice (text)
                - asset_allocation: category-wise breakdown
                - charts_data: pre-formatted data for Plotly charts
                - audit_entries: list of all logged actions
        """
        analysis_start = time.perf_counter()
        results: Dict[str, Any] = {}
        audit_entries: List[str] = []

        # ── Step 0: Log analysis start ────────────────────────────────────
        entry_id = self.audit_logger.log(
            agent_name=self.AGENT_NAME,
            action="analysis_started",
            input_summary=f"PDF: {cams_pdf_path}, Risk: {risk_profile}",
            output_summary="Pipeline initiated",
            tools_called=[],
        )
        audit_entries.append(entry_id)

        try:
            # ── Step 1: Parse CAMS PDF ────────────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "parse_cams_pdf",
                input_summary=f"Parsing {cams_pdf_path}",
            ) as tracker:
                transactions_df, holdings_df = self._parse_portfolio(cams_pdf_path)
                num_txns = len(transactions_df)
                num_funds = holdings_df["fund_name"].nunique()
                tracker.set_output(
                    f"Extracted {num_txns} transactions across {num_funds} funds"
                )
                tracker.set_tools(["pdfplumber", "pandas"] if _HAS_PDF_PARSER else ["fallback_demo_data"])

            # ── Step 2: Per-fund XIRR ─────────────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "compute_xirr_per_fund",
                input_summary=f"Computing XIRR for {num_funds} funds",
            ) as tracker:
                xirr_by_fund = self._compute_xirr_per_fund(transactions_df, holdings_df)
                best_fund = max(xirr_by_fund, key=lambda f: xirr_by_fund[f]["xirr_pct"])
                tracker.set_output(
                    f"Best: {best_fund} at {xirr_by_fund[best_fund]['xirr_pct']:.1f}% XIRR"
                )
                tracker.set_tools(["scipy.optimize.brentq"] if _HAS_FINANCIAL_CALC else ["fallback_cagr"])
            results["xirr_by_fund"] = xirr_by_fund

            # ── Step 3: Portfolio-level XIRR ──────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "compute_portfolio_xirr",
                input_summary="Aggregating all cashflows for portfolio XIRR",
            ) as tracker:
                portfolio_xirr = self._compute_portfolio_xirr(transactions_df, holdings_df)
                tracker.set_output(f"Portfolio XIRR: {portfolio_xirr * 100:.2f}%")
                tracker.set_tools(["scipy.optimize.brentq"] if _HAS_FINANCIAL_CALC else ["fallback_cagr"])
            results["portfolio_xirr"] = portfolio_xirr

            # ── Step 4: Overlap Analysis ──────────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "compute_overlap",
                input_summary=f"Checking overlap between {num_funds} funds",
            ) as tracker:
                overlap = self._compute_overlap(holdings_df)
                tracker.set_output(
                    f"Highest overlap: {overlap['highest_overlap_pct'] * 100:.1f}% "
                    f"between {overlap['highest_overlap_pair']}"
                )
                tracker.set_tools(["jaccard_similarity"])
            results["overlap_analysis"] = overlap

            # ── Step 5: Expense Drag ──────────────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "compute_expense_drag",
                input_summary="Calculating expense ratio impact over 10 years",
            ) as tracker:
                expense = self._compute_expense_analysis(holdings_df)
                tracker.set_output(
                    f"Annual fees: ₹{expense['annual_fees_total']:,.0f}, "
                    f"10yr drag: ₹{expense['ten_year_drag']:,.0f}"
                )
                tracker.set_tools(["compounding_math"])
            results["expense_analysis"] = expense

            # ── Step 6: Benchmark Comparison ──────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "benchmark_comparison",
                input_summary=f"Comparing portfolio XIRR {portfolio_xirr * 100:.2f}% vs benchmarks",
            ) as tracker:
                benchmark = self._benchmark_comparison(portfolio_xirr)
                beats_nifty = benchmark["comparisons"].get("Nifty 50", {}).get("alpha_pct", 0)
                tracker.set_output(
                    f"Alpha vs Nifty 50: {beats_nifty:+.2f}%"
                )
                tracker.set_tools(["benchmark_data"])
            results["benchmark_comparison"] = benchmark

            # ── Step 7: Asset Allocation ──────────────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "compute_asset_allocation",
                input_summary="Computing category-wise allocation",
            ) as tracker:
                allocation = self._compute_asset_allocation(holdings_df)
                tracker.set_output(
                    f"Categories: {', '.join(f'{k}: {v:.0f}%' for k, v in allocation.items())}"
                )
                tracker.set_tools(["pandas"])
            results["asset_allocation"] = allocation

            # ── Step 8: Portfolio Summary ─────────────────────────────────
            total_invested = holdings_df["invested_value"].sum()
            total_current = holdings_df["current_value"].sum()
            absolute_gain = total_current - total_invested
            absolute_return_pct = (absolute_gain / total_invested * 100) if total_invested > 0 else 0

            results["portfolio_summary"] = {
                "total_invested": round(total_invested, 0),
                "total_current_value": round(total_current, 0),
                "absolute_gain": round(absolute_gain, 0),
                "absolute_return_pct": round(absolute_return_pct, 2),
                "portfolio_xirr_pct": round(portfolio_xirr * 100, 2),
                "num_funds": num_funds,
                "num_transactions": num_txns,
                "risk_profile": risk_profile,
            }

            # ── Step 9: LLM Rebalancing Advice ───────────────────────────
            with self.audit_logger.track(
                self.AGENT_NAME, "generate_rebalancing_plan",
                input_summary=f"LLM generating advice for {risk_profile} risk profile",
            ) as tracker:
                rebalancing = self._generate_rebalancing_plan(
                    holdings_df, overlap, xirr_by_fund, risk_profile
                )
                word_count = len(rebalancing.split())
                tracker.set_output(f"Generated {word_count}-word rebalancing plan")
                tracker.set_tools(["gemini-1.5-pro", "rag_knowledge_base"])
            results["rebalancing_plan"] = rebalancing

            # ── Step 10: Format for Streamlit ─────────────────────────────
            results["charts_data"] = self._prepare_charts_data(results)

        except Exception as e:
            error_msg = f"Portfolio analysis failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.audit_logger.log(
                agent_name=self.AGENT_NAME,
                action="analysis_failed",
                input_summary=f"PDF: {cams_pdf_path}",
                output_summary=error_msg,
                status="error",
                error_detail=traceback.format_exc(),
            )
            results["error_message"] = error_msg

        # ── Final audit log ───────────────────────────────────────────────
        total_ms = int((time.perf_counter() - analysis_start) * 1000)
        self.audit_logger.log(
            agent_name=self.AGENT_NAME,
            action="analysis_completed",
            input_summary=f"PDF: {cams_pdf_path}, Risk: {risk_profile}",
            output_summary=(
                f"Completed in {total_ms}ms. "
                f"Funds: {results.get('portfolio_summary', {}).get('num_funds', 'N/A')}, "
                f"XIRR: {results.get('portfolio_xirr', 0) * 100:.2f}%"
            ),
            tools_called=["pdf_parser", "scipy", "pandas", "gemini"],
            duration_ms=total_ms,
        )

        results["audit_entries"] = audit_entries
        return results

    # ── Sub-step 1: Parse CAMS PDF ────────────────────────────────────────

    def _parse_portfolio(
        self, pdf_path: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Parse a CAMS Consolidated Account Statement PDF into structured DataFrames.

        Uses CAMSParser from tools/pdf_parser.py if available, otherwise falls
        back to realistic demo data for development/demo purposes.

        Parameters:
            pdf_path (str): Path to the uploaded CAMS PDF file.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - transactions_df: columns [fund_name, date, amount, units, nav, type]
                - holdings_df: columns [fund_name, units, nav, current_value, invested_value, category]

        Raises:
            ValueError: If parsed data is empty or invalid.
        """
        if _HAS_PDF_PARSER:
            # Use teammate's PDF parser
            parser = CAMSParser()
            transactions_df, holdings_df = parser.parse(pdf_path)
        else:
            # Fallback to demo data
            transactions_df, holdings_df = _fallback_parse_cams(pdf_path)

        # ── Data validation ───────────────────────────────────────────────
        if transactions_df.empty:
            raise ValueError("No transactions found in the CAMS PDF.")
        if holdings_df.empty:
            raise ValueError("No current holdings found in the CAMS PDF.")

        # Ensure required columns
        required_txn_cols = {"fund_name", "date", "amount"}
        required_hold_cols = {"fund_name", "current_value", "invested_value"}

        missing_txn = required_txn_cols - set(transactions_df.columns)
        if missing_txn:
            raise ValueError(f"Transaction data missing columns: {missing_txn}")

        missing_hold = required_hold_cols - set(holdings_df.columns)
        if missing_hold:
            raise ValueError(f"Holdings data missing columns: {missing_hold}")

        # Ensure dates are date objects
        if not pd.api.types.is_datetime64_any_dtype(transactions_df["date"]):
            transactions_df["date"] = pd.to_datetime(transactions_df["date"]).dt.date

        logger.info(
            f"Parsed portfolio: {len(transactions_df)} transactions, "
            f"{len(holdings_df)} holdings across {holdings_df['fund_name'].nunique()} funds."
        )
        return transactions_df, holdings_df

    # ── Sub-step 2: Per-fund XIRR ─────────────────────────────────────────

    def _compute_xirr_per_fund(
        self,
        transactions: pd.DataFrame,
        holdings: pd.DataFrame,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate annualized XIRR for each individual mutual fund.

        For each fund:
            - Gathers all transaction cashflows (investments as negative)
            - Appends current value as final positive cashflow (today's date)
            - Runs XIRR calculation

        Parameters:
            transactions (pd.DataFrame): Transaction history.
            holdings (pd.DataFrame): Current fund holdings.

        Returns:
            Dict[str, Dict]: Per-fund dict with xirr_pct, invested_amount,
                             current_value, absolute_return_pct, investment_period_years.
        """
        xirr_func = calculate_xirr if _HAS_FINANCIAL_CALC else _fallback_xirr
        results: Dict[str, Dict[str, Any]] = {}
        today = date.today()

        for _, holding in holdings.iterrows():
            fund_name = holding["fund_name"]
            current_value = holding["current_value"]
            invested_value = holding["invested_value"]

            # Get all transactions for this fund
            fund_txns = transactions[transactions["fund_name"] == fund_name].copy()
            fund_txns = fund_txns.sort_values("date")

            if fund_txns.empty:
                results[fund_name] = {
                    "xirr_pct": 0.0,
                    "invested_amount": invested_value,
                    "current_value": current_value,
                    "absolute_return_pct": 0.0,
                    "investment_period_years": 0.0,
                }
                continue

            # Build cashflow arrays
            cashflows: List[float] = fund_txns["amount"].tolist()
            dates: List[date] = [
                d if isinstance(d, date) else d.date() if hasattr(d, "date") else d
                for d in fund_txns["date"].tolist()
            ]

            # Append current value as final positive cashflow
            cashflows.append(current_value)
            dates.append(today)

            # Calculate XIRR
            try:
                xirr_decimal = xirr_func(cashflows, dates)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"XIRR failed for {fund_name}: {e}. Using CAGR fallback.")
                xirr_decimal = _fallback_xirr(cashflows, dates)

            # Calculate supplementary metrics
            abs_return_pct = (
                ((current_value - invested_value) / invested_value * 100)
                if invested_value > 0 else 0.0
            )
            first_date = min(dates)
            period_years = (today - first_date).days / 365.25

            results[fund_name] = {
                "xirr_pct": round(xirr_decimal * 100, 2),
                "invested_amount": round(invested_value, 0),
                "current_value": round(current_value, 0),
                "absolute_return_pct": round(abs_return_pct, 2),
                "investment_period_years": round(period_years, 1),
            }

        return results

    # ── Sub-step 3: Portfolio-level XIRR ──────────────────────────────────

    def _compute_portfolio_xirr(
        self,
        transactions: pd.DataFrame,
        holdings: pd.DataFrame,
    ) -> float:
        """
        Calculate the overall portfolio XIRR by combining all fund cashflows
        into a single stream.

        Parameters:
            transactions (pd.DataFrame): All transactions across all funds.
            holdings (pd.DataFrame): Current holdings for all funds.

        Returns:
            float: Portfolio-level annualized XIRR as decimal (e.g. 0.14 = 14%).
        """
        xirr_func = calculate_xirr if _HAS_FINANCIAL_CALC else _fallback_xirr
        today = date.today()

        # All investment cashflows (negative)
        all_cashflows: List[float] = transactions["amount"].tolist()
        all_dates: List[date] = [
            d if isinstance(d, date) else d.date() if hasattr(d, "date") else d
            for d in transactions["date"].tolist()
        ]

        # Add total current value as single positive cashflow today
        total_current_value = holdings["current_value"].sum()
        all_cashflows.append(total_current_value)
        all_dates.append(today)

        try:
            return xirr_func(all_cashflows, all_dates)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Portfolio XIRR failed: {e}. Using CAGR fallback.")
            return _fallback_xirr(all_cashflows, all_dates)

    # ── Sub-step 4: Overlap Analysis ──────────────────────────────────────

    def _compute_overlap(
        self, holdings: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect underlying stock overlap across mutual funds using Jaccard similarity.

        Uses the hardcoded FUND_HOLDINGS_DATABASE for top-10 holdings of known
        Indian funds. For unknown funds, uses a generic set.

        Parameters:
            holdings (pd.DataFrame): Current fund holdings with fund_name column.

        Returns:
            Dict: overlap_matrix, highest_overlap_pair, highest_overlap_pct, recommendation.
        """
        overlap_func = calculate_portfolio_overlap if _HAS_FINANCIAL_CALC else _fallback_overlap

        # Build holdings dict from our reference database
        fund_names = holdings["fund_name"].unique().tolist()
        fund_holdings_for_analysis: Dict[str, List[str]] = {}

        for fund in fund_names:
            # Try exact match first, then fuzzy match
            matched = False
            for db_fund, stocks in FUND_HOLDINGS_DATABASE.items():
                if fund.lower() in db_fund.lower() or db_fund.lower() in fund.lower():
                    fund_holdings_for_analysis[fund] = stocks
                    matched = True
                    break

            if not matched:
                # Assign generic holdings for unknown funds
                fund_holdings_for_analysis[fund] = [
                    "HDFC Bank", "ICICI Bank", "Infosys", "TCS", "Reliance Industries"
                ]
                logger.warning(
                    f"Fund '{fund}' not in reference database. Using generic holdings."
                )

        if len(fund_holdings_for_analysis) < 2:
            return {
                "overlap_matrix": {},
                "highest_overlap_pair": ("", ""),
                "highest_overlap_pct": 0.0,
                "recommendation": "Need at least 2 funds for overlap analysis.",
            }

        return overlap_func(fund_holdings_for_analysis)

    # ── Sub-step 5: Expense Analysis ──────────────────────────────────────

    def _compute_expense_analysis(
        self, holdings: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate the annual fee burden and 10-year compounding drag
        of expense ratios across the portfolio.

        Parameters:
            holdings (pd.DataFrame): Current holdings with fund_name and current_value.

        Returns:
            Dict: annual_fees_total, ten_year_drag, worst_fund, best_alternative_saving.
        """
        expense_func = calculate_expense_drag if _HAS_FINANCIAL_CALC else _fallback_expense_drag

        portfolio_items: List[Dict[str, Any]] = []
        for _, row in holdings.iterrows():
            fund_name = row["fund_name"]

            # Look up expense ratio from our reference data
            expense_ratio = None
            for db_fund, er in FUND_EXPENSE_RATIOS.items():
                if fund_name.lower() in db_fund.lower() or db_fund.lower() in fund_name.lower():
                    expense_ratio = er
                    break

            if expense_ratio is None:
                expense_ratio = 0.75  # Default for unknown funds
                logger.warning(
                    f"Expense ratio for '{fund_name}' not found. Defaulting to 0.75%."
                )

            portfolio_items.append({
                "fund_name": fund_name,
                "current_value": row["current_value"],
                "expense_ratio": expense_ratio,
            })

        return expense_func(portfolio_items)

    # ── Sub-step 6: Benchmark Comparison ──────────────────────────────────

    def _benchmark_comparison(
        self, portfolio_xirr: float
    ) -> Dict[str, Any]:
        """
        Compare the portfolio's XIRR against major Indian market benchmarks.

        Parameters:
            portfolio_xirr (float): Portfolio XIRR as decimal (e.g. 0.14).

        Returns:
            Dict with:
                - portfolio_xirr_pct: float
                - comparisons: Dict[benchmark_name → {benchmark_return_pct, alpha_pct, verdict}]
                - overall_verdict: str
        """
        portfolio_pct = portfolio_xirr * 100
        comparisons: Dict[str, Dict[str, Any]] = {}

        for benchmark_name, benchmark_return in BENCHMARK_RETURNS.items():
            benchmark_pct = benchmark_return * 100
            alpha = portfolio_pct - benchmark_pct

            if alpha > 2.0:
                verdict = "Outperforming ✅"
            elif alpha > -1.0:
                verdict = "In line ≈"
            else:
                verdict = "Underperforming ❌"

            comparisons[benchmark_name] = {
                "benchmark_return_pct": round(benchmark_pct, 2),
                "alpha_pct": round(alpha, 2),
                "verdict": verdict,
            }

        # Overall verdict
        nifty_alpha = comparisons.get("Nifty 50", {}).get("alpha_pct", 0)
        if nifty_alpha > 2:
            overall = (
                f"Your portfolio is generating {nifty_alpha:.1f}% alpha over Nifty 50. "
                f"Excellent fund selection!"
            )
        elif nifty_alpha > -1:
            overall = (
                f"Your portfolio is roughly in line with Nifty 50 ({nifty_alpha:+.1f}% difference). "
                f"Consider whether active funds justify their higher expense ratios."
            )
        else:
            overall = (
                f"Your portfolio is underperforming Nifty 50 by {abs(nifty_alpha):.1f}%. "
                f"A simple index fund might serve you better. Review underperforming funds."
            )

        return {
            "portfolio_xirr_pct": round(portfolio_pct, 2),
            "comparisons": comparisons,
            "overall_verdict": overall,
        }

    # ── Sub-step 7: Asset Allocation ──────────────────────────────────────

    def _compute_asset_allocation(
        self, holdings: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate category-wise asset allocation percentages.

        Parameters:
            holdings (pd.DataFrame): Holdings with current_value and category columns.

        Returns:
            Dict[str, float]: Category → allocation percentage.
        """
        if "category" not in holdings.columns:
            return {"Unknown": 100.0}

        total = holdings["current_value"].sum()
        if total <= 0:
            return {"Unknown": 100.0}

        allocation = (
            holdings.groupby("category")["current_value"]
            .sum()
            .apply(lambda x: round(x / total * 100, 1))
            .to_dict()
        )

        return allocation

    # ── Sub-step 8: LLM Rebalancing Plan ──────────────────────────────────

    def _generate_rebalancing_plan(
        self,
        holdings: pd.DataFrame,
        overlap: Dict[str, Any],
        xirr_by_fund: Dict[str, Dict[str, Any]],
        risk_profile: str,
    ) -> str:
        """
        Generate personalized rebalancing recommendations using Gemini LLM.

        The LLM receives ONLY pre-computed data and must base its advice
        strictly on those numbers. No independent financial calculations.

        Parameters:
            holdings (pd.DataFrame): Current fund holdings.
            overlap (Dict): Overlap analysis results.
            xirr_by_fund (Dict): Per-fund XIRR data.
            risk_profile (str): "conservative", "moderate", or "aggressive".

        Returns:
            str: Markdown-formatted rebalancing recommendation.
        """
        # ── Build data context for the LLM ────────────────────────────────
        holdings_summary = []
        for _, row in holdings.iterrows():
            fname = row["fund_name"]
            fund_xirr = xirr_by_fund.get(fname, {})
            holdings_summary.append(
                f"- {fname} ({row.get('category', 'N/A')}): "
                f"Invested ₹{row['invested_value']:,.0f}, "
                f"Current ₹{row['current_value']:,.0f}, "
                f"XIRR {fund_xirr.get('xirr_pct', 0):.1f}%"
            )

        # Identify underperformers (below category average)
        underperformers = [
            f for f, data in xirr_by_fund.items()
            if data.get("xirr_pct", 0) < 10.0  # Below 10% considered weak
        ]

        # Retrieve SEBI rules from knowledge base if available
        retrieved_rules = ""
        if self.knowledge_base and _HAS_RAG:
            try:
                docs = self.knowledge_base.query(
                    "SEBI mutual fund rebalancing guidelines portfolio diversification rules India"
                )
                retrieved_rules = "\n".join(
                    [doc.page_content for doc in docs[:3]]
                ) if docs else "No specific SEBI rules retrieved."
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")
                retrieved_rules = "RAG unavailable. Use general SEBI guidelines."
        else:
            retrieved_rules = (
                "General SEBI Guidelines:\n"
                "- Diversify across at least 3-4 fund categories.\n"
                "- Avoid more than 40% overlap between any two funds.\n"
                "- Review underperforming funds every 12 months.\n"
                "- Prefer direct plans over regular plans.\n"
                "- Limit individual fund allocation to 25-30% of portfolio."
            )

        # ── Construct prompt ──────────────────────────────────────────────
        prompt = f"""You are a SEBI-registered investment analyst advising an Indian retail investor.
Based ONLY on the following pre-computed data (do NOT use outside knowledge or make up numbers),
generate a specific, actionable portfolio rebalancing recommendation.

## PORTFOLIO DATA:
{chr(10).join(holdings_summary)}

## OVERLAP FINDINGS:
- Highest overlap: {overlap['highest_overlap_pct'] * 100:.1f}% between {overlap['highest_overlap_pair']}
- Recommendation: {overlap['recommendation']}

## UNDERPERFORMING FUNDS (XIRR < 10%):
{', '.join(underperformers) if underperformers else 'None — all funds performing adequately.'}

## INVESTOR RISK PROFILE: {risk_profile.upper()}

## APPLICABLE SEBI RULES:
{retrieved_rules}

## FORMAT YOUR RESPONSE AS:
### 1. Funds to Exit (with specific reason and data from above)
### 2. Funds to Increase Allocation (with reason)
### 3. New Fund Categories to Consider (category only — NOT specific fund names per SEBI guidelines)
### 4. Suggested Target Allocation (percentages by category, must add to 100%)
### 5. Action Timeline (what to do this month vs next quarter)

Keep the total response under 400 words. Use ₹ for all amounts. Be specific — cite the exact numbers from the data above."""

        # ── Call LLM ──────────────────────────────────────────────────────
        try:
            response = self.llm.invoke(prompt)
            # Handle different LLM response formats
            if hasattr(response, "content"):
                return response.content
            return str(response)
        except Exception as e:
            logger.error(f"LLM rebalancing generation failed: {e}")
            # Return structured fallback if LLM fails
            return self._fallback_rebalancing_plan(
                holdings, overlap, xirr_by_fund, underperformers, risk_profile
            )

    def _fallback_rebalancing_plan(
        self,
        holdings: pd.DataFrame,
        overlap: Dict[str, Any],
        xirr_by_fund: Dict[str, Dict[str, Any]],
        underperformers: List[str],
        risk_profile: str,
    ) -> str:
        """
        Generate rule-based rebalancing advice when the LLM is unavailable.

        Parameters:
            holdings (pd.DataFrame): Current holdings.
            overlap (Dict): Overlap analysis.
            xirr_by_fund (Dict): Per-fund performance.
            underperformers (List[str]): Funds below threshold.
            risk_profile (str): Risk tolerance.

        Returns:
            str: Markdown-formatted rebalancing advice.
        """
        lines = ["## Portfolio Rebalancing Recommendations\n"]
        lines.append("*(Generated using rule-based analysis — LLM was unavailable)*\n")

        # Funds to exit
        lines.append("### 1. Funds to Review for Exit")
        if underperformers:
            for fund in underperformers:
                data = xirr_by_fund[fund]
                lines.append(
                    f"- **{fund}**: XIRR of {data['xirr_pct']:.1f}% is below the 10% threshold. "
                    f"Invested ₹{data['invested_amount']:,.0f}, current ₹{data['current_value']:,.0f}."
                )
        else:
            lines.append("- No funds flagged for exit. All performing above threshold.")

        # Overlap warning
        lines.append("\n### 2. Overlap Alert")
        if overlap["highest_overlap_pct"] > 0.25:
            pair = overlap["highest_overlap_pair"]
            lines.append(
                f"- **{pair[0]}** and **{pair[1]}** share "
                f"{overlap['highest_overlap_pct'] * 100:.1f}% holdings. "
                f"Consider consolidating."
            )
        else:
            lines.append("- No significant overlap detected. Good diversification.")

        # Risk-based allocation targets
        lines.append("\n### 3. Suggested Target Allocation")
        targets = {
            "conservative": {"Large Cap": 50, "Flexi Cap": 20, "Mid Cap": 15, "Small Cap": 5, "Debt": 10},
            "moderate": {"Large Cap": 35, "Flexi Cap": 25, "Mid Cap": 20, "Small Cap": 10, "Debt": 10},
            "aggressive": {"Large Cap": 20, "Flexi Cap": 20, "Mid Cap": 25, "Small Cap": 25, "Debt": 10},
        }
        target = targets.get(risk_profile, targets["moderate"])
        for cat, pct in target.items():
            lines.append(f"- {cat}: {pct}%")

        return "\n".join(lines)

    # ── Charts Data Formatter ─────────────────────────────────────────────

    def _prepare_charts_data(
        self, results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare pre-formatted data structures for Plotly/Streamlit charts.

        Parameters:
            results (Dict): Complete analysis results.

        Returns:
            Dict with chart-ready data for each visualization.
        """
        charts: Dict[str, Any] = {}

        # 1. Fund-wise XIRR bar chart
        xirr_data = results.get("xirr_by_fund", {})
        charts["xirr_bar"] = {
            "fund_names": list(xirr_data.keys()),
            "xirr_values": [d["xirr_pct"] for d in xirr_data.values()],
            "colors": [
                "#22c55e" if d["xirr_pct"] > 12 else "#f59e0b" if d["xirr_pct"] > 8 else "#ef4444"
                for d in xirr_data.values()
            ],
        }

        # 2. Asset allocation pie chart
        charts["allocation_pie"] = results.get("asset_allocation", {})

        # 3. Invested vs Current value comparison
        charts["value_comparison"] = {
            "labels": list(xirr_data.keys()),
            "invested": [d["invested_amount"] for d in xirr_data.values()],
            "current": [d["current_value"] for d in xirr_data.values()],
        }

        # 4. Benchmark comparison
        benchmark = results.get("benchmark_comparison", {}).get("comparisons", {})
        charts["benchmark_bar"] = {
            "benchmarks": list(benchmark.keys()),
            "benchmark_returns": [d["benchmark_return_pct"] for d in benchmark.values()],
            "portfolio_return": results.get("benchmark_comparison", {}).get("portfolio_xirr_pct", 0),
        }

        return charts

    # ── LangGraph Node Interface ──────────────────────────────────────────

    def as_langgraph_node(self):
        """
        Return a callable function compatible with LangGraph's StateGraph.add_node().

        Usage:
            from agents.portfolio_agent import PortfolioAgent
            agent = PortfolioAgent(llm=llm, audit_logger=logger)
            workflow.add_node("portfolio_xray", agent.as_langgraph_node())

        Returns:
            Callable[[FinSaarthiState], Dict]: Node function.
        """

        def node_fn(state: FinSaarthiState) -> Dict[str, Any]:
            """
            LangGraph node that reads from state, runs analysis, writes results back.

            Parameters:
                state (FinSaarthiState): Current graph state.

            Returns:
                Dict: State update with portfolio_data and final_response populated.
            """
            pdf_path = state.get("uploaded_file_path", "")
            risk_profile = state.get("user_profile", {}).get("risk_tolerance", "moderate")

            if not pdf_path:
                return {
                    "error_message": "No CAMS PDF uploaded. Please upload your portfolio statement.",
                    "portfolio_data": {},
                }

            try:
                analysis = self.analyze(pdf_path, risk_profile)

                # Map analysis results to state's PortfolioData namespace
                portfolio_data: PortfolioData = {
                    "xirr_results": {
                        fund: data["xirr_pct"]
                        for fund, data in analysis.get("xirr_by_fund", {}).items()
                    },
                    "overlap_matrix": analysis.get("overlap_analysis", {}).get("overlap_matrix", {}),
                    "rebalancing_suggestions": [{"plan": analysis.get("rebalancing_plan", "")}],
                    "total_current_value": analysis.get("portfolio_summary", {}).get("total_current_value", 0),
                    "total_invested": analysis.get("portfolio_summary", {}).get("total_invested", 0),
                    "asset_allocation": analysis.get("asset_allocation", {}),
                }

                return {
                    "portfolio_data": portfolio_data,
                    "agent_results": analysis,
                    "final_response": self._format_markdown_response(analysis),
                    "error_message": "",
                }

            except Exception as e:
                return {
                    "error_message": f"Portfolio analysis failed: {str(e)}",
                    "portfolio_data": {},
                }

        return node_fn

    # ── Markdown Response Formatter ───────────────────────────────────────

    def _format_markdown_response(self, analysis: Dict[str, Any]) -> str:
        """
        Convert raw analysis into a clean markdown response for the user.

        Parameters:
            analysis (Dict): Complete analysis results from self.analyze().

        Returns:
            str: Markdown-formatted summary.
        """
        summary = analysis.get("portfolio_summary", {})
        xirr_data = analysis.get("xirr_by_fund", {})
        benchmark = analysis.get("benchmark_comparison", {})

        lines = [
            "# 📊 Portfolio X-Ray Report\n",
            "## Summary",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Invested | ₹{summary.get('total_invested', 0):,.0f} |",
            f"| Current Value | ₹{summary.get('total_current_value', 0):,.0f} |",
            f"| Absolute Gain | ₹{summary.get('absolute_gain', 0):,.0f} ({summary.get('absolute_return_pct', 0):.1f}%) |",
            f"| Portfolio XIRR | {summary.get('portfolio_xirr_pct', 0):.2f}% |",
            f"| Number of Funds | {summary.get('num_funds', 0)} |",
            "",
            "## Fund-wise Performance",
            "| Fund | Invested | Current | XIRR | Period |",
            "|------|----------|---------|------|--------|",
        ]

        for fund, data in xirr_data.items():
            lines.append(
                f"| {fund} | ₹{data['invested_amount']:,.0f} | "
                f"₹{data['current_value']:,.0f} | {data['xirr_pct']:.1f}% | "
                f"{data['investment_period_years']:.1f} yrs |"
            )

        lines.append(f"\n## Benchmark Comparison")
        lines.append(benchmark.get("overall_verdict", ""))

        lines.append(f"\n{analysis.get('rebalancing_plan', '')}")

        return "\n".join(lines)
