"""
FinSaarthi — Tax Wizard Agent (Module 3)
==========================================
Analyzes salary structure, compares Old vs New tax regimes, identifies
missed deductions, and recommends tax-saving investments.

Accepts either a Form 16 PDF or manual salary inputs.
ALL tax math in Python. LLM only for natural language action plan.

File: agents/tax_agent.py
Branch: feature/agents
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional

from state import FinSaarthiState, TaxData
from tools.audit_logger import AuditLogger

try:
    from tools.financial_calc import compare_tax_regimes, calculate_hra_exemption
    _HAS_CALC = True
except ImportError:
    _HAS_CALC = False

try:
    from tools.pdf_parser import Form16Parser
    _HAS_PARSER = True
except ImportError:
    _HAS_PARSER = False

try:
    from rag.knowledge_base import FinancialKnowledgeBase
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False

logger = logging.getLogger("finsaarthi.tax_agent")

# ── FY 2024-25 Constants ─────────────────────────────────────────────────────
LIMITS = {
    "80C": 150000, "80D_self": 25000, "80D_parents": 50000, "80D_senior": 50000,
    "80CCD1B": 50000, "HRA_metro_pct": 0.50, "HRA_nonmetro_pct": 0.40,
    "std_deduction_old": 50000, "std_deduction_new": 75000,
    "home_loan_24b": 200000, "80EE": 50000,
}

# ── Tax Slab Functions (fallback if tools not merged) ────────────────────────

def _fb_hra(basic: float, hra_recv: float, rent: float, is_metro: bool) -> float:
    if rent <= 0 or hra_recv <= 0:
        return 0.0
    c1 = hra_recv
    c2 = max(0, rent - 0.10 * basic)
    c3 = (0.50 if is_metro else 0.40) * basic
    return min(c1, c2, c3)

def _fb_old_tax(taxable: float) -> float:
    if taxable <= 500000:
        return 0.0
    tax = 0.0
    if taxable > 1000000:
        tax += (taxable - 1000000) * 0.30 + 500000 * 0.20 + 250000 * 0.05
    elif taxable > 500000:
        tax += (taxable - 500000) * 0.20 + 250000 * 0.05
    else:
        tax += (taxable - 250000) * 0.05
    return tax * 1.04

def _fb_new_tax(taxable: float) -> float:
    if taxable <= 700000:
        return 0.0
    tax = 0.0
    slabs = [(1500000, 0.30), (1200000, 0.20), (1000000, 0.15), (700000, 0.10), (300000, 0.05)]
    remaining = taxable
    for threshold, rate in slabs:
        if remaining > threshold:
            tax += (remaining - threshold) * rate
            remaining = threshold
    return tax * 1.04

def _fb_compare(gross: float, basic: float, hra_recv: float, rent: float,
                city: str, d80c: float, d80d: float, nps: float, home_loan: float, other: float) -> Dict[str, Any]:
    is_metro = city.lower() == "metro"
    hra_ex = _fb_hra(basic, hra_recv, rent, is_metro)
    old_ded = hra_ex + 50000 + min(d80c, 150000) + min(nps, 50000) + min(d80d, 75000) + min(home_loan, 200000) + other
    taxable_old = max(0, gross - old_ded)
    tax_old = _fb_old_tax(taxable_old)
    taxable_new = max(0, gross - 75000)
    tax_new = _fb_new_tax(taxable_new)
    missed = []
    if d80c < 150000:
        missed.append({"section": "80C", "gap": 150000 - d80c, "tip": "ELSS, PPF, or EPF top-up."})
    if nps < 50000:
        missed.append({"section": "80CCD(1B)", "gap": 50000 - nps, "tip": "NPS Tier-1 for additional ₹50k."})
    if d80d < 25000:
        missed.append({"section": "80D", "gap": 25000 - d80d, "tip": "Health insurance premium."})
    rec = "New Regime" if tax_new <= tax_old else "Old Regime"
    return {"old_tax": round(tax_old), "new_tax": round(tax_new), "old_net_salary": round(gross - tax_old),
            "new_net_salary": round(gross - tax_new), "recommended_regime": rec, "savings_amount": round(abs(tax_old - tax_new)),
            "missed_deductions_list": missed, "taxable_old": round(taxable_old), "taxable_new": round(taxable_new)}

def _fb_parse_form16(path: str) -> Dict[str, Any]:
    """Demo salary data when Form16 parser not available."""
    logger.warning("Form16 parser not available. Using demo data.")
    return {"gross_salary": 1200000, "basic": 500000, "hra_received": 250000,
            "rent_paid": 300000, "city_type": "metro", "deductions_80c_used": 80000,
            "deductions_80d_used": 0, "nps_used": 0, "home_loan_interest": 0, "other_deductions": 0}

# ── Tax-Saving Investment Database ───────────────────────────────────────────
TAX_INVESTMENTS = [
    {"name": "ELSS Mutual Fund", "section": "80C", "max_amount": 150000, "expected_return": 0.12,
     "lock_in_years": 3, "risk_level": "moderate-high", "liquidity": "3yr lock-in"},
    {"name": "PPF (Public Provident Fund)", "section": "80C", "max_amount": 150000, "expected_return": 0.071,
     "lock_in_years": 15, "risk_level": "zero", "liquidity": "15yr, partial from yr 7"},
    {"name": "NPS Tier-1", "section": "80CCD(1B)", "max_amount": 50000, "expected_return": 0.10,
     "lock_in_years": 25, "risk_level": "moderate", "liquidity": "till 60, partial at 60"},
    {"name": "Tax-Saver FD", "section": "80C", "max_amount": 150000, "expected_return": 0.065,
     "lock_in_years": 5, "risk_level": "zero", "liquidity": "5yr lock-in"},
    {"name": "SSY (Sukanya Samriddhi)", "section": "80C", "max_amount": 150000, "expected_return": 0.082,
     "lock_in_years": 21, "risk_level": "zero", "liquidity": "21yr, partial from 18yr"},
    {"name": "NSC (National Savings Certificate)", "section": "80C", "max_amount": 150000, "expected_return": 0.073,
     "lock_in_years": 5, "risk_level": "zero", "liquidity": "5yr lock-in"},
    {"name": "Health Insurance (Self+Family)", "section": "80D", "max_amount": 25000, "expected_return": 0.0,
     "lock_in_years": 1, "risk_level": "zero", "liquidity": "annual"},
    {"name": "Health Insurance (Parents 60+)", "section": "80D", "max_amount": 50000, "expected_return": 0.0,
     "lock_in_years": 1, "risk_level": "zero", "liquidity": "annual"},
    {"name": "Home Loan Principal", "section": "80C", "max_amount": 150000, "expected_return": 0.0,
     "lock_in_years": 0, "risk_level": "zero", "liquidity": "ongoing EMI"},
    {"name": "Home Loan Interest", "section": "24(b)", "max_amount": 200000, "expected_return": 0.0,
     "lock_in_years": 0, "risk_level": "zero", "liquidity": "ongoing EMI"},
]


class TaxAgent:
    """
    Module 3: Tax Wizard Agent.

    Pipeline: Parse Form16/manual inputs → Regime comparison → Deduction audit →
              Investment recommendations → Net impact → LLM action plan.

    Parameters:
        llm: LangChain-compatible LLM (Gemini 1.5 Pro).
        knowledge_base: RAG knowledge base for tax rules.
        audit_logger: SQLite audit trail.
    """

    AGENT_NAME: str = "tax_agent"

    def __init__(self, llm: Any, knowledge_base: Any = None, audit_logger: Optional[AuditLogger] = None) -> None:
        self.llm = llm
        self.knowledge_base = knowledge_base
        self.audit_logger = audit_logger or AuditLogger()
        logger.info("TaxAgent initialized.")

    # ══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════

    def analyze(self, form16_path: str = None, manual_inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run complete tax analysis pipeline.

        Parameters:
            form16_path (str, optional): Path to Form 16 PDF.
            manual_inputs (dict, optional): Manual salary data.

        Returns:
            Dict with regime_comparison, missed_deductions, investment_recommendations,
            net_impact, action_plan, charts_data.
        """
        start = time.perf_counter()
        results: Dict[str, Any] = {}
        self.audit_logger.log(self.AGENT_NAME, "analysis_started",
                              input_summary=f"Form16: {form16_path or 'N/A'}, Manual: {'Yes' if manual_inputs else 'No'}")

        try:
            # Step 1: Get salary data
            with self.audit_logger.track(self.AGENT_NAME, "extract_salary_data") as t:
                if form16_path:
                    salary_data = self._parse_form16(form16_path)
                elif manual_inputs:
                    salary_data = manual_inputs
                else:
                    raise ValueError("Provide either form16_path or manual_inputs.")
                t.set_output(f"Gross: ₹{salary_data.get('gross_salary', 0):,.0f}")
                t.set_tools(["form16_parser"] if form16_path else ["manual_input"])
            results["salary_data"] = salary_data

            # Step 2: Regime comparison
            with self.audit_logger.track(self.AGENT_NAME, "compare_regimes") as t:
                regime = self._compute_regime_comparison(salary_data)
                t.set_output(f"Old: ₹{regime['old_tax']:,.0f}, New: ₹{regime['new_tax']:,.0f} → {regime['recommended_regime']}")
                t.set_tools(["tax_slab_calculator"])
            results["regime_comparison"] = regime

            # Step 3: Deduction audit
            with self.audit_logger.track(self.AGENT_NAME, "audit_deductions") as t:
                missed = self._audit_existing_deductions(salary_data)
                total_gap = sum(d["gap_amount"] for d in missed)
                t.set_output(f"Found {len(missed)} missed deductions, gap: ₹{total_gap:,.0f}")
                t.set_tools(["deduction_rules"])
            results["missed_deductions"] = missed

            # Step 4: Investment recommendations
            with self.audit_logger.track(self.AGENT_NAME, "find_investments") as t:
                investments = self._find_investment_opportunities(salary_data, missed)
                t.set_output(f"Ranked {len(investments)} investment options")
                t.set_tools(["investment_db", "rag"])
            results["investment_recommendations"] = investments

            # Step 5: Net impact
            with self.audit_logger.track(self.AGENT_NAME, "calculate_net_impact") as t:
                optimized_tax = self._compute_optimized_tax(salary_data, missed)
                current_best = min(regime["old_tax"], regime["new_tax"])
                impact = self._calculate_net_impact(current_best, optimized_tax, investments)
                t.set_output(f"Potential saving: ₹{impact['total_tax_saving']:,.0f}")
                t.set_tools(["tax_math"])
            results["net_impact"] = impact

            # Step 6: Tax calendar
            results["tax_calendar"] = self._tax_calendar()

            # Step 7: LLM action plan
            with self.audit_logger.track(self.AGENT_NAME, "generate_action_plan") as t:
                plan = self._generate_action_plan(results)
                t.set_output(f"Generated {len(plan.split())}-word action plan")
                t.set_tools(["gemini-1.5-pro", "rag"])
            results["action_plan"] = plan

            # Step 8: Charts
            results["charts_data"] = self._prepare_charts_data(results)

        except Exception as e:
            logger.error(traceback.format_exc())
            self.audit_logger.log(self.AGENT_NAME, "analysis_failed", status="error", error_detail=str(e))
            results["error_message"] = str(e)

        elapsed = int((time.perf_counter() - start) * 1000)
        self.audit_logger.log(self.AGENT_NAME, "analysis_completed", duration_ms=elapsed,
                              output_summary=f"Done in {elapsed}ms")
        return results

    # ══════════════════════════════════════════════════════════════════════
    # STEP 1: PARSE FORM 16
    # ══════════════════════════════════════════════════════════════════════

    def _parse_form16(self, pdf_path: str) -> Dict[str, Any]:
        """Extract salary data from Form 16 PDF."""
        if _HAS_PARSER:
            parser = Form16Parser()
            return parser.parse(pdf_path)
        return _fb_parse_form16(pdf_path)

    # ══════════════════════════════════════════════════════════════════════
    # STEP 2: REGIME COMPARISON
    # ══════════════════════════════════════════════════════════════════════

    def _compute_regime_comparison(self, s: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare Old vs New tax regimes using exact FY24-25 slabs.

        Parameters:
            s (dict): Salary data with all deduction fields.

        Returns:
            Dict with old_tax, new_tax, recommended_regime, savings_amount, etc.
        """
        compare_fn = compare_tax_regimes if _HAS_CALC else _fb_compare
        return compare_fn(
            s.get("gross_salary", 0), s.get("basic", 0), s.get("hra_received", 0),
            s.get("rent_paid", 0), s.get("city_type", "metro"),
            s.get("deductions_80c_used", 0), s.get("deductions_80d_used", 0),
            s.get("nps_used", 0), s.get("home_loan_interest", 0), s.get("other_deductions", 0),
        )

    # ══════════════════════════════════════════════════════════════════════
    # STEP 3: DEDUCTION AUDIT
    # ══════════════════════════════════════════════════════════════════════

    def _audit_existing_deductions(self, s: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Audit each deduction section to find unclaimed amounts.

        Parameters:
            s (dict): Salary data.

        Returns:
            List of dicts: deduction_name, section, max_allowed, currently_claimed,
            gap_amount, tax_saving_possible, action_required.
        """
        gross = s.get("gross_salary", 0)
        # Determine tax bracket for savings calculation
        if gross > 1500000:
            bracket = 0.312  # 30% + 4% cess
        elif gross > 1000000:
            bracket = 0.208  # 20% + cess
        elif gross > 500000:
            bracket = 0.052  # 5% + cess
        else:
            bracket = 0.0

        missed: List[Dict[str, Any]] = []

        # 80C
        used_80c = s.get("deductions_80c_used", 0)
        if used_80c < LIMITS["80C"]:
            gap = LIMITS["80C"] - used_80c
            missed.append({
                "deduction_name": "Section 80C (ELSS/PPF/EPF/Insurance)",
                "section": "80C", "max_allowed": LIMITS["80C"], "currently_claimed": used_80c,
                "gap_amount": gap, "tax_saving_possible": round(gap * bracket),
                "action_required": "Invest in ELSS MF (best returns) or PPF (safest) before March 31st.",
            })

        # 80D — Self
        used_80d = s.get("deductions_80d_used", 0)
        if used_80d < LIMITS["80D_self"]:
            gap = LIMITS["80D_self"] - used_80d
            missed.append({
                "deduction_name": "Section 80D — Health Insurance (Self & Family)",
                "section": "80D", "max_allowed": LIMITS["80D_self"], "currently_claimed": used_80d,
                "gap_amount": gap, "tax_saving_possible": round(gap * bracket),
                "action_required": "Buy a ₹10L+ health insurance policy. It's tax-saving AND essential protection.",
            })

        # 80D — Parents (often overlooked)
        parents_80d = s.get("deductions_80d_parents", 0)
        if parents_80d < LIMITS["80D_parents"]:
            gap = LIMITS["80D_parents"] - parents_80d
            missed.append({
                "deduction_name": "Section 80D — Parents Health Insurance",
                "section": "80D", "max_allowed": LIMITS["80D_parents"], "currently_claimed": parents_80d,
                "gap_amount": gap, "tax_saving_possible": round(gap * bracket),
                "action_required": "Pay parents' health insurance premium for additional ₹50K deduction (₹25K if non-senior).",
            })

        # 80CCD(1B) — NPS
        nps_used = s.get("nps_used", 0)
        if nps_used < LIMITS["80CCD1B"]:
            gap = LIMITS["80CCD1B"] - nps_used
            missed.append({
                "deduction_name": "Section 80CCD(1B) — NPS Additional",
                "section": "80CCD(1B)", "max_allowed": LIMITS["80CCD1B"], "currently_claimed": nps_used,
                "gap_amount": gap, "tax_saving_possible": round(gap * bracket),
                "action_required": "Open NPS Tier-1 account. ₹50K deduction OVER AND ABOVE 80C. Highest impact per rupee.",
            })

        # HRA check
        basic = s.get("basic", 0)
        hra_recv = s.get("hra_received", 0)
        rent = s.get("rent_paid", 0)
        is_metro = s.get("city_type", "metro").lower() == "metro"
        if rent > 0 and hra_recv > 0:
            hra_fn = calculate_hra_exemption if _HAS_CALC else _fb_hra
            optimal_hra = hra_fn(basic, hra_recv, rent, is_metro)
            current_hra = s.get("hra_exemption_claimed", optimal_hra)
            if current_hra < optimal_hra * 0.95:  # 5% tolerance
                gap = optimal_hra - current_hra
                missed.append({
                    "deduction_name": "HRA Exemption", "section": "HRA",
                    "max_allowed": round(optimal_hra), "currently_claimed": round(current_hra),
                    "gap_amount": round(gap), "tax_saving_possible": round(gap * bracket),
                    "action_required": "Ensure rent receipts are submitted. Optimal HRA exemption: ₹{:,.0f}.".format(optimal_hra),
                })
        elif rent > 0 and hra_recv == 0:
            missed.append({
                "deduction_name": "HRA / Section 80GG", "section": "80GG",
                "max_allowed": 60000, "currently_claimed": 0, "gap_amount": 60000,
                "tax_saving_possible": round(60000 * bracket),
                "action_required": "No HRA in salary but paying rent? Claim 80GG (max ₹5,000/month).",
            })

        # Home Loan Interest
        home_loan = s.get("home_loan_interest", 0)
        if 0 < home_loan < LIMITS["home_loan_24b"]:
            gap = LIMITS["home_loan_24b"] - home_loan
            missed.append({
                "deduction_name": "Home Loan Interest — Section 24(b)", "section": "24(b)",
                "max_allowed": LIMITS["home_loan_24b"], "currently_claimed": home_loan,
                "gap_amount": gap, "tax_saving_possible": round(gap * bracket),
                "action_required": "Ensure full home loan interest is claimed. Get certificate from bank.",
            })

        return missed

    # ══════════════════════════════════════════════════════════════════════
    # STEP 4: INVESTMENT RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════

    def _find_investment_opportunities(self, salary_data: Dict[str, Any], missed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank tax-saving investments based on user's tax bracket and risk profile.

        Parameters:
            salary_data: Salary data for bracket calculation.
            missed: Missed deductions to match investments against.

        Returns:
            Ranked list of investment recommendations.
        """
        gross = salary_data.get("gross_salary", 0)
        risk = salary_data.get("risk_profile", "moderate")

        if gross > 1500000:
            bracket = 0.312
        elif gross > 1000000:
            bracket = 0.208
        elif gross > 500000:
            bracket = 0.052
        else:
            bracket = 0.0

        missed_sections = {d["section"] for d in missed}
        recommendations: List[Dict[str, Any]] = []

        for inv in TAX_INVESTMENTS:
            if inv["section"] not in missed_sections and inv["section"] not in ("80C", "80CCD(1B)", "80D"):
                continue

            effective_return = self._compute_effective_return(inv, bracket)
            # Risk-based ranking score
            risk_penalty = {"zero": 0, "moderate": 1, "moderate-high": 2, "high": 3}.get(inv["risk_level"], 1)
            if risk == "aggressive":
                risk_penalty = -risk_penalty  # Aggressive investors prefer higher risk
            elif risk == "conservative":
                risk_penalty *= 2

            # Higher return + tax benefit = better rank
            rank_score = effective_return * 100 - risk_penalty

            gap_for_section = sum(d["gap_amount"] for d in missed if d["section"] == inv["section"])
            invest_amount = min(inv["max_amount"], gap_for_section) if gap_for_section > 0 else inv["max_amount"]

            recommendations.append({
                "investment_name": inv["name"], "section": inv["section"],
                "max_amount": inv["max_amount"], "recommended_amount": invest_amount,
                "expected_return": inv["expected_return"],
                "effective_return_with_tax": round(effective_return, 4),
                "lock_in_years": inv["lock_in_years"], "risk_level": inv["risk_level"],
                "tax_saving_amount": round(invest_amount * bracket),
                "rank_score": round(rank_score, 2),
            })

        recommendations.sort(key=lambda x: x["rank_score"], reverse=True)
        for i, rec in enumerate(recommendations):
            rec["recommendation_rank"] = i + 1

        return recommendations

    # ══════════════════════════════════════════════════════════════════════
    # STEP 5: EFFECTIVE RETURN + NET IMPACT
    # ══════════════════════════════════════════════════════════════════════

    def _compute_effective_return(self, investment: Dict[str, Any], tax_bracket: float) -> float:
        """
        Calculate effective return including tax benefit.
        Effective = stated_return + tax_bracket (since investment itself saves tax).

        Parameters:
            investment: Investment dict with expected_return.
            tax_bracket: Marginal tax rate.

        Returns:
            float: Effective annualized return.
        """
        return investment.get("expected_return", 0) + (tax_bracket / max(investment.get("lock_in_years", 1), 1))

    def _compute_optimized_tax(self, salary_data: Dict[str, Any], missed: List[Dict[str, Any]]) -> float:
        """Calculate tax if ALL missed deductions are utilized (Old Regime)."""
        total_new_deductions = sum(d["gap_amount"] for d in missed)
        optimized_80c = min(salary_data.get("deductions_80c_used", 0) + total_new_deductions, 150000)

        compare_fn = compare_tax_regimes if _HAS_CALC else _fb_compare
        optimized = compare_fn(
            salary_data.get("gross_salary", 0), salary_data.get("basic", 0),
            salary_data.get("hra_received", 0), salary_data.get("rent_paid", 0),
            salary_data.get("city_type", "metro"), optimized_80c,
            min(salary_data.get("deductions_80d_used", 0) + 25000, 75000),
            min(salary_data.get("nps_used", 0) + 50000, 50000),
            salary_data.get("home_loan_interest", 0), salary_data.get("other_deductions", 0),
        )
        return min(optimized["old_tax"], optimized["new_tax"])

    def _calculate_net_impact(self, current_tax: float, optimized_tax: float, investments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate the net financial impact of implementing all recommendations.

        Parameters:
            current_tax: Current best-regime tax.
            optimized_tax: Tax after maximizing all deductions.
            investments: Recommended investments.

        Returns:
            Dict with tax savings breakdown and net cash impact.
        """
        tax_saved = max(0, current_tax - optimized_tax)
        total_investment_needed = sum(inv["recommended_amount"] for inv in investments)
        monthly_investment = total_investment_needed / 12

        return {
            "current_tax": round(current_tax),
            "optimized_tax": round(optimized_tax),
            "total_tax_saving": round(tax_saved),
            "monthly_tax_saving": round(tax_saved / 12),
            "total_investment_needed": round(total_investment_needed),
            "monthly_investment_needed": round(monthly_investment),
            "net_monthly_benefit": round(tax_saved / 12 - monthly_investment),
            "roi_pct": round((tax_saved / total_investment_needed * 100), 1) if total_investment_needed > 0 else 0,
        }

    # ══════════════════════════════════════════════════════════════════════
    # TAX CALENDAR
    # ══════════════════════════════════════════════════════════════════════

    def _tax_calendar(self) -> List[Dict[str, str]]:
        """Key tax deadlines for FY 2024-25."""
        return [
            {"date": "March 31", "event": "Last date for 80C/80D investments for current FY", "priority": "🔴 Critical"},
            {"date": "June 15", "event": "Advance Tax — 1st installment (15%)", "priority": "🟡 Important"},
            {"date": "July 31", "event": "ITR filing deadline (non-audit)", "priority": "🔴 Critical"},
            {"date": "September 15", "event": "Advance Tax — 2nd installment (45% cumulative)", "priority": "🟡 Important"},
            {"date": "October 31", "event": "ITR filing deadline (audit cases)", "priority": "🟡 Important"},
            {"date": "December 15", "event": "Advance Tax — 3rd installment (75% cumulative)", "priority": "🟡 Important"},
            {"date": "December 31", "event": "Belated/revised return deadline", "priority": "🟠 Moderate"},
            {"date": "March 15", "event": "Advance Tax — 4th installment (100%)", "priority": "🟡 Important"},
        ]

    # ══════════════════════════════════════════════════════════════════════
    # LLM ACTION PLAN
    # ══════════════════════════════════════════════════════════════════════

    def _generate_action_plan(self, results: Dict[str, Any]) -> str:
        """Generate a CA-quality action plan using Gemini."""
        regime = results.get("regime_comparison", {})
        missed = results.get("missed_deductions", [])
        impact = results.get("net_impact", {})
        investments = results.get("investment_recommendations", [])

        missed_text = "\n".join([f"- {d['deduction_name']}: gap ₹{d['gap_amount']:,.0f} → saves ₹{d['tax_saving_possible']:,.0f}" for d in missed])
        inv_text = "\n".join([f"- #{i['recommendation_rank']} {i['investment_name']} (₹{i['recommended_amount']:,.0f}, {i['risk_level']} risk)" for i in investments[:5]])

        rules = ""
        if self.knowledge_base and _HAS_RAG:
            try:
                docs = self.knowledge_base.query("Indian income tax deductions 80C 80D NPS regime comparison FY2024-25")
                rules = "\n".join([d.page_content for d in docs[:3]]) if docs else ""
            except Exception:
                pass
        if not rules:
            rules = ("- 80C limit: ₹1.5L (ELSS, PPF, EPF, LIC, tuition). - 80CCD(1B): additional ₹50K for NPS.\n"
                     "- 80D: ₹25K self + ₹50K senior parents. - New regime: 75K std deduction only.\n"
                     "- ELSS has 3yr lock-in but best historical returns among 80C options.")

        prompt = f"""You are a chartered accountant advising an Indian salaried employee.
Based ONLY on the following computed tax analysis (numbers are already calculated — do NOT recalculate), write a specific action plan.

REGIME COMPARISON:
- Old Regime Tax: ₹{regime.get('old_tax', 0):,.0f}
- New Regime Tax: ₹{regime.get('new_tax', 0):,.0f}
- Recommended: {regime.get('recommended_regime', 'N/A')}
- Savings by right regime: ₹{regime.get('savings_amount', 0):,.0f}

MISSED DEDUCTIONS:
{missed_text or 'None — all deductions maximized!'}

TOP INVESTMENTS:
{inv_text}

NET IMPACT:
- Total potential tax saving: ₹{impact.get('total_tax_saving', 0):,.0f}/year
- Investment needed: ₹{impact.get('total_investment_needed', 0):,.0f}

TAX RULES:
{rules}

FORMAT: List actions in priority order:
1) Do IMMEDIATELY (this week)
2) Before March 31st
3) Next financial year planning
Keep under 400 words. Use ₹ for all amounts. Be specific with amounts."""

        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"LLM action plan failed: {e}")
            return self._fallback_action_plan(results)

    def _fallback_action_plan(self, results: Dict[str, Any]) -> str:
        """Rule-based action plan when LLM unavailable."""
        missed = results.get("missed_deductions", [])
        regime = results.get("regime_comparison", {})
        impact = results.get("net_impact", {})
        lines = [f"## Tax Optimization Action Plan\n*(Rule-based — LLM unavailable)*\n",
                 f"**Recommended Regime:** {regime.get('recommended_regime', 'N/A')} — saves ₹{regime.get('savings_amount', 0):,.0f}/year\n",
                 "### Immediate Actions:"]
        for d in missed[:3]:
            lines.append(f"- **{d['deduction_name']}**: Invest ₹{d['gap_amount']:,.0f} → save ₹{d['tax_saving_possible']:,.0f} tax")
        lines.append(f"\n**Total potential saving: ₹{impact.get('total_tax_saving', 0):,.0f}/year**")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════
    # CHARTS DATA
    # ══════════════════════════════════════════════════════════════════════

    def _prepare_charts_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare Streamlit/Plotly chart data."""
        regime = results.get("regime_comparison", {})
        missed = results.get("missed_deductions", [])
        return {
            "regime_bar": {"labels": ["Old Regime", "New Regime"], "values": [regime.get("old_tax", 0), regime.get("new_tax", 0)]},
            "deductions_gap": {"sections": [d["section"] for d in missed], "gaps": [d["gap_amount"] for d in missed], "savings": [d["tax_saving_possible"] for d in missed]},
            "net_salary_comparison": {"labels": ["Current", "Optimized"], "values": [regime.get("old_net_salary", 0) if regime.get("recommended_regime") == "Old Regime" else regime.get("new_net_salary", 0), regime.get("old_net_salary", 0) if regime.get("recommended_regime") == "Old Regime" else regime.get("new_net_salary", 0)]},
        }

    # ══════════════════════════════════════════════════════════════════════
    # LANGGRAPH NODE INTERFACE
    # ══════════════════════════════════════════════════════════════════════

    def as_langgraph_node(self):
        """Return callable for LangGraph StateGraph.add_node()."""
        def node_fn(state: FinSaarthiState) -> Dict[str, Any]:
            pdf_path = state.get("uploaded_file_path")
            profile = state.get("user_profile", {})
            manual = {"gross_salary": profile.get("annual_income", 0), "basic": profile.get("annual_income", 0) * 0.4,
                      "hra_received": profile.get("annual_income", 0) * 0.2, "rent_paid": 0,
                      "city_type": profile.get("city", "metro"), "deductions_80c_used": 0,
                      "deductions_80d_used": 0, "nps_used": 0, "home_loan_interest": 0, "other_deductions": 0} if not pdf_path else None

            analysis = self.analyze(form16_path=pdf_path, manual_inputs=manual)
            regime = analysis.get("regime_comparison", {})

            tax_data: TaxData = {
                "parsed_income": {"gross_salary": analysis.get("salary_data", {}).get("gross_salary", 0)},
                "declared_deductions": {"80C": analysis.get("salary_data", {}).get("deductions_80c_used", 0)},
                "missed_deductions": analysis.get("missed_deductions", []),
                "old_regime_tax": regime.get("old_tax", 0), "new_regime_tax": regime.get("new_tax", 0),
                "recommended_regime": regime.get("recommended_regime", ""),
                "tax_saving_potential": analysis.get("net_impact", {}).get("total_tax_saving", 0),
                "section_wise_analysis": {"regime": regime, "deductions": analysis.get("missed_deductions", [])},
            }
            return {"tax_data": tax_data, "agent_results": analysis,
                    "final_response": analysis.get("action_plan", ""), "error_message": analysis.get("error_message", "")}
        return node_fn
