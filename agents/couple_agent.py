"""
FinSaarthi — Couple's Money Planner Agent (Module 4)
=====================================================
The differentiator module. Optimizes dual-income household finances:
joint tax planning, HRA allocation, NPS maximization, SIP splitting,
and combined net worth tracking.

ALL math in Python. LLM only for personalized narrative.

File: agents/couple_agent.py
Branch: feature/agents
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional

from state import FinSaarthiState, CoupleData
from tools.audit_logger import AuditLogger

try:
    from tools.financial_calc import compare_tax_regimes, calculate_hra_exemption, calculate_sip_for_goal
    _HAS_CALC = True
except ImportError:
    _HAS_CALC = False

try:
    from rag.knowledge_base import FinancialKnowledgeBase
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False

logger = logging.getLogger("finsaarthi.couple_agent")

# ── Fallback tax/HRA functions ───────────────────────────────────────────────

def _fb_hra(basic: float, hra_recv: float, rent: float, is_metro: bool) -> float:
    if rent <= 0 or hra_recv <= 0:
        return 0.0
    return min(hra_recv, max(0, rent - 0.10 * basic), (0.50 if is_metro else 0.40) * basic)

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
    rem = taxable
    for th, rate in slabs:
        if rem > th:
            tax += (rem - th) * rate
            rem = th
    return tax * 1.04

def _fb_best_tax(gross: float, basic: float, hra_recv: float, rent: float,
                 city: str, d80c: float, d80d: float, nps: float, home_loan: float) -> float:
    """Return minimum of old/new regime tax."""
    is_metro = city.lower() == "metro"
    hra_ex = _fb_hra(basic, hra_recv, rent, is_metro)
    old_ded = hra_ex + 50000 + min(d80c, 150000) + min(nps, 50000) + min(d80d, 75000) + min(home_loan, 200000)
    tax_old = _fb_old_tax(max(0, gross - old_ded))
    tax_new = _fb_new_tax(max(0, gross - 75000))
    return min(tax_old, tax_new)

def _get_bracket(gross: float) -> float:
    if gross > 1500000: return 0.312
    if gross > 1000000: return 0.208
    if gross > 500000: return 0.052
    return 0.0

def _fb_sip(goal_today: float, years: int, ret: float, inf: float, savings: float = 0) -> Dict[str, float]:
    fv = goal_today * ((1 + inf) ** years)
    fv_sav = savings * ((1 + ret) ** years)
    shortfall = max(0, fv - fv_sav)
    if shortfall <= 0:
        return {"monthly_sip": 0, "future_goal_value": fv}
    mr = ret / 12
    n = years * 12
    sip = shortfall * mr / (((1 + mr) ** n) - 1) if mr > 0 else shortfall / n
    return {"monthly_sip": round(sip, 0), "future_goal_value": round(fv, 0)}


class CoupleAgent:
    """
    Module 4: Couple's Money Planner.

    Pipeline: Identify earners → HRA optimization → 80C allocation →
              NPS both → Combined net worth → SIP allocation →
              Total optimization → LLM couple plan.
    """

    AGENT_NAME: str = "couple_agent"

    def __init__(self, llm: Any, knowledge_base: Any = None, audit_logger: Optional[AuditLogger] = None) -> None:
        self.llm = llm
        self.knowledge_base = knowledge_base
        self.audit_logger = audit_logger or AuditLogger()
        logger.info("CoupleAgent initialized.")

    # ══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════

    def optimize(self, partner1: Dict[str, Any], partner2: Dict[str, Any], shared_goals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run complete couple optimization pipeline.

        Parameters:
            partner1 (dict): Keys: name, age, gross_salary, basic, hra_received, rent_paid,
                city, deductions_80c, deductions_80d, nps_existing, existing_investments, risk_profile.
            partner2 (dict): Same schema.
            shared_goals (list): [{name, amount, years}, ...].

        Returns:
            Dict with all optimization results, narrative, and charts data.
        """
        start = time.perf_counter()
        results: Dict[str, Any] = {}
        p1_name = partner1.get("name", "Partner 1")
        p2_name = partner2.get("name", "Partner 2")

        self.audit_logger.log(self.AGENT_NAME, "optimization_started",
                              input_summary=f"{p1_name} (₹{partner1.get('gross_salary',0):,.0f}) + {p2_name} (₹{partner2.get('gross_salary',0):,.0f})")

        try:
            # Step 1: Identify higher earner
            with self.audit_logger.track(self.AGENT_NAME, "identify_earners") as t:
                higher = self._identify_higher_earner(partner1, partner2)
                t.set_output(f"Higher earner: {higher}")
            results["higher_earner"] = higher

            # Step 2: HRA optimization
            with self.audit_logger.track(self.AGENT_NAME, "optimize_hra") as t:
                hra = self._optimize_hra(partner1, partner2)
                t.set_output(f"Best: {hra['best_scenario']}, saves ₹{hra['combined_tax_saving']:,.0f}")
                t.set_tools(["hra_calculator"])
            results["hra_optimization"] = hra

            # Step 3: 80C allocation
            with self.audit_logger.track(self.AGENT_NAME, "optimize_80c") as t:
                sec80c = self._optimize_80c_allocation(partner1, partner2)
                t.set_output(f"Combined saving: ₹{sec80c['combined_tax_saving']:,.0f}")
                t.set_tools(["tax_slab_calculator"])
            results["section_80c_optimization"] = sec80c

            # Step 4: NPS both partners
            with self.audit_logger.track(self.AGENT_NAME, "optimize_nps") as t:
                nps = self._optimize_nps_both(partner1, partner2)
                t.set_output(f"NPS saving: ₹{nps['combined_tax_saving']:,.0f}")
                t.set_tools(["nps_calculator"])
            results["nps_optimization"] = nps

            # Step 5: Combined net worth
            with self.audit_logger.track(self.AGENT_NAME, "calculate_net_worth") as t:
                nw = self._calculate_combined_net_worth(partner1, partner2)
                t.set_output(f"Net worth: ₹{nw['net_worth']:,.0f}")
                t.set_tools(["asset_calculator"])
            results["net_worth"] = nw

            # Step 6: SIP allocation
            with self.audit_logger.track(self.AGENT_NAME, "optimize_sip") as t:
                sip = self._optimize_sip_allocation(partner1, partner2, shared_goals)
                t.set_output(f"P1 SIP: ₹{sip['p1_total_sip']:,.0f}, P2 SIP: ₹{sip['p2_total_sip']:,.0f}")
                t.set_tools(["sip_calculator"])
            results["sip_allocation"] = sip

            # Step 7: Total optimization score
            with self.audit_logger.track(self.AGENT_NAME, "total_optimization") as t:
                total = self._calculate_total_optimization(results, partner1, partner2)
                t.set_output(f"Score: {total['optimization_score']}/100, Annual saving: ₹{total['total_annual_tax_saving']:,.0f}")
            results["total_optimization"] = total

            # Step 8: LLM narrative
            with self.audit_logger.track(self.AGENT_NAME, "generate_plan") as t:
                narrative = self._generate_couple_plan(results, partner1, partner2)
                t.set_output(f"Generated {len(narrative.split())}-word plan")
                t.set_tools(["gemini-1.5-pro"])
            results["narrative"] = narrative

            # Step 9: Charts
            results["charts_data"] = self._prepare_charts_data(results, partner1, partner2)

        except Exception as e:
            logger.error(traceback.format_exc())
            self.audit_logger.log(self.AGENT_NAME, "optimization_failed", status="error", error_detail=str(e))
            results["error_message"] = str(e)

        elapsed = int((time.perf_counter() - start) * 1000)
        self.audit_logger.log(self.AGENT_NAME, "optimization_completed", duration_ms=elapsed)
        return results

    # ══════════════════════════════════════════════════════════════════════
    # STEP 1: IDENTIFY HIGHER EARNER
    # ══════════════════════════════════════════════════════════════════════

    def _identify_higher_earner(self, p1: Dict, p2: Dict) -> str:
        """Return name of higher earner. Critical for HRA and 80C strategy."""
        g1, g2 = p1.get("gross_salary", 0), p2.get("gross_salary", 0)
        return p1.get("name", "Partner 1") if g1 >= g2 else p2.get("name", "Partner 2")

    # ══════════════════════════════════════════════════════════════════════
    # STEP 2: HRA OPTIMIZATION
    # ══════════════════════════════════════════════════════════════════════

    def _optimize_hra(self, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """
        Test 3 rent allocation scenarios and find maximum combined HRA exemption.

        Scenarios:
            A: 100% rent in P1's name (current default)
            B: 100% rent in P2's name
            C: Split 60/40 (higher earner gets 60%)
        """
        hra_fn = calculate_hra_exemption if _HAS_CALC else _fb_hra
        total_rent = p1.get("rent_paid", 0) + p2.get("rent_paid", 0)
        if total_rent <= 0:
            return {"best_scenario": "No rent paid", "p1_hra_exemption": 0, "p2_hra_exemption": 0,
                    "combined_tax_saving": 0, "action_required": "N/A — neither partner pays rent."}

        b1, b2 = p1.get("basic", 0), p2.get("basic", 0)
        h1, h2 = p1.get("hra_received", 0), p2.get("hra_received", 0)
        m1 = p1.get("city", "metro").lower() == "metro"
        m2 = p2.get("city", "metro").lower() == "metro"
        br1, br2 = _get_bracket(p1.get("gross_salary", 0)), _get_bracket(p2.get("gross_salary", 0))

        scenarios: Dict[str, Dict[str, Any]] = {}

        # Scenario A: All rent in P1
        hra_a1 = hra_fn(b1, h1, total_rent, m1)
        hra_a2 = 0
        tax_a = hra_a1 * br1

        # Scenario B: All rent in P2
        hra_b1 = 0
        hra_b2 = hra_fn(b2, h2, total_rent, m2)
        tax_b = hra_b2 * br2

        # Scenario C: Split 60/40 (higher earner gets 60%)
        if p1.get("gross_salary", 0) >= p2.get("gross_salary", 0):
            r1, r2 = total_rent * 0.6, total_rent * 0.4
        else:
            r1, r2 = total_rent * 0.4, total_rent * 0.6
        hra_c1 = hra_fn(b1, h1, r1, m1)
        hra_c2 = hra_fn(b2, h2, r2, m2)
        tax_c = hra_c1 * br1 + hra_c2 * br2

        scenarios = {
            "A: All rent in P1 name": {"p1": hra_a1, "p2": hra_a2, "saving": round(tax_a)},
            "B: All rent in P2 name": {"p1": hra_b1, "p2": hra_b2, "saving": round(tax_b)},
            "C: Split 60/40": {"p1": hra_c1, "p2": hra_c2, "saving": round(tax_c)},
        }

        best_name = max(scenarios, key=lambda k: scenarios[k]["saving"])
        best = scenarios[best_name]
        current_saving = round(hra_fn(b1, h1, p1.get("rent_paid", 0), m1) * br1 + hra_fn(b2, h2, p2.get("rent_paid", 0), m2) * br2)
        additional = best["saving"] - current_saving

        return {
            "best_scenario": best_name,
            "all_scenarios": scenarios,
            "p1_hra_exemption": round(best["p1"]),
            "p2_hra_exemption": round(best["p2"]),
            "combined_tax_saving": round(best["saving"]),
            "additional_vs_current": max(0, additional),
            "action_required": f"Switch to '{best_name}' for optimal HRA benefit." if additional > 0 else "Current arrangement is optimal.",
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 3: 80C ALLOCATION
    # ══════════════════════════════════════════════════════════════════════

    def _optimize_80c_allocation(self, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """
        Optimize 80C allocation: each partner can claim up to ₹1.5L.
        Combined cap = ₹3L. Higher bracket partner should max out first.
        """
        g1, g2 = p1.get("gross_salary", 0), p2.get("gross_salary", 0)
        used1, used2 = p1.get("deductions_80c", 0), p2.get("deductions_80c", 0)
        gap1, gap2 = max(0, 150000 - used1), max(0, 150000 - used2)
        br1, br2 = _get_bracket(g1), _get_bracket(g2)

        # Current tax saved via 80C
        current_saving = used1 * br1 + used2 * br2

        # Optimal: fill higher bracket first
        opt1 = min(150000, used1 + gap1) if br1 >= br2 else used1
        opt2 = min(150000, used2 + gap2) if br2 > br1 else min(150000, used2 + gap2)
        # If higher earner has room and lower earner's 80C can be shifted
        if br1 > br2 and gap1 > 0:
            opt1 = 150000
        if br2 > br1 and gap2 > 0:
            opt2 = 150000

        optimized_saving = opt1 * br1 + opt2 * br2
        additional = max(0, optimized_saving - current_saving)

        return {
            "p1_80c_current": used1, "p1_80c_optimal": opt1, "p1_gap": gap1,
            "p2_80c_current": used2, "p2_80c_optimal": opt2, "p2_gap": gap2,
            "combined_limit": 300000,
            "combined_current": used1 + used2,
            "combined_optimal": opt1 + opt2,
            "current_combined_tax_saving": round(current_saving),
            "optimized_combined_tax_saving": round(optimized_saving),
            "combined_tax_saving": round(additional),
            "action": f"Max out 80C for both partners. Additional investment needed: ₹{gap1 + gap2:,.0f}.",
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 4: NPS OPTIMIZATION
    # ══════════════════════════════════════════════════════════════════════

    def _optimize_nps_both(self, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """
        80CCD(1B): Each partner gets additional ₹50K NPS deduction.
        Combined maximum = ₹1L additional deduction.
        """
        nps1 = p1.get("nps_existing", 0)
        nps2 = p2.get("nps_existing", 0)
        gap1 = max(0, 50000 - nps1)
        gap2 = max(0, 50000 - nps2)
        br1, br2 = _get_bracket(p1.get("gross_salary", 0)), _get_bracket(p2.get("gross_salary", 0))

        saving1 = gap1 * br1
        saving2 = gap2 * br2
        combined = saving1 + saving2

        return {
            "p1_nps_current": nps1, "p1_nps_additional": gap1, "p1_tax_saving": round(saving1),
            "p2_nps_current": nps2, "p2_nps_additional": gap2, "p2_tax_saving": round(saving2),
            "combined_tax_saving": round(combined),
            "monthly_nps_needed_p1": round(gap1 / 12),
            "monthly_nps_needed_p2": round(gap2 / 12),
            "combined_monthly_nps": round((gap1 + gap2) / 12),
            "action": "Both partners should open NPS Tier-1 accounts. Set up auto-debit of ₹{:,.0f}/month each.".format(max(gap1, gap2) / 12),
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 5: COMBINED NET WORTH
    # ══════════════════════════════════════════════════════════════════════

    def _calculate_combined_net_worth(self, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """
        Calculate household net worth: total assets - total liabilities.
        """
        def _sum_investments(p: Dict) -> float:
            inv = p.get("existing_investments", {})
            return sum(inv.values()) if isinstance(inv, dict) else float(inv or 0)

        def _sum_liabilities(p: Dict) -> float:
            liab = p.get("liabilities", {})
            return sum(liab.values()) if isinstance(liab, dict) else float(liab or 0)

        assets1, assets2 = _sum_investments(p1), _sum_investments(p2)
        liab1, liab2 = _sum_liabilities(p1), _sum_liabilities(p2)

        total_assets = assets1 + assets2
        total_liab = liab1 + liab2
        net_worth = total_assets - total_liab

        # FIRE target (both partners): combined monthly expenses × 12 / 4% SWR
        combined_expenses = p1.get("monthly_expenses", 50000) + p2.get("monthly_expenses", 50000)
        retirement_target = combined_expenses * 12 / 0.04

        return {
            "p1_assets": round(assets1), "p2_assets": round(assets2),
            "total_assets": round(total_assets),
            "p1_liabilities": round(liab1), "p2_liabilities": round(liab2),
            "total_liabilities": round(total_liab),
            "net_worth": round(net_worth),
            "retirement_target": round(retirement_target),
            "net_worth_gap": round(max(0, retirement_target - net_worth)),
            "net_worth_pct_of_target": round(net_worth / retirement_target * 100, 1) if retirement_target > 0 else 0,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 6: SIP ALLOCATION
    # ══════════════════════════════════════════════════════════════════════

    def _optimize_sip_allocation(self, p1: Dict, p2: Dict, goals: List[Dict]) -> Dict[str, Any]:
        """
        Allocate SIPs across both partners for each shared goal.
        Strategy: Higher earner invests more for LTCG harvesting.
        Both get ₹1L LTCG exemption = ₹2L combined tax-free gains.
        """
        sip_fn = calculate_sip_for_goal if _HAS_CALC else _fb_sip
        g1, g2 = p1.get("gross_salary", 0), p2.get("gross_salary", 0)
        surplus1 = g1 / 12 - p1.get("monthly_expenses", g1 * 0.4 / 12)
        surplus2 = g2 / 12 - p2.get("monthly_expenses", g2 * 0.4 / 12)
        total_surplus = surplus1 + surplus2

        # Proportion based on surplus
        p1_ratio = surplus1 / total_surplus if total_surplus > 0 else 0.5
        p2_ratio = 1 - p1_ratio

        sip_by_goal: List[Dict[str, Any]] = []
        p1_total, p2_total = 0.0, 0.0

        for goal in goals:
            years = goal.get("years", 5)
            ret = 0.14 if years >= 7 else 0.12 if years >= 5 else 0.08
            result = sip_fn(goal.get("amount", 0), years, ret, 0.06, 0)
            total_sip = result["monthly_sip"]

            p1_sip = round(total_sip * p1_ratio, 0)
            p2_sip = round(total_sip * p2_ratio, 0)
            p1_total += p1_sip
            p2_total += p2_sip

            sip_by_goal.append({
                "goal_name": goal.get("name", "Goal"),
                "total_sip": total_sip,
                "p1_sip": p1_sip, "p2_sip": p2_sip,
                "future_value": result["future_goal_value"],
                "years": years,
            })

        return {
            "p1_total_sip": round(p1_total), "p2_total_sip": round(p2_total),
            "combined_total_sip": round(p1_total + p2_total),
            "sip_by_goal": sip_by_goal,
            "combined_ltcg_exemption": 200000,
            "ltcg_note": "Both partners get ₹1L LTCG exemption each. Split investments to maximize tax-free gains.",
            "p1_surplus": round(surplus1), "p2_surplus": round(surplus2),
            "p1_utilization_pct": round(p1_total / surplus1 * 100, 1) if surplus1 > 0 else 0,
            "p2_utilization_pct": round(p2_total / surplus2 * 100, 1) if surplus2 > 0 else 0,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 7: TOTAL OPTIMIZATION SCORE
    # ══════════════════════════════════════════════════════════════════════

    def _calculate_total_optimization(self, results: Dict, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """Sum all savings and compute a 0-100 optimization score."""
        hra_saving = results.get("hra_optimization", {}).get("additional_vs_current", 0)
        sec80c_saving = results.get("section_80c_optimization", {}).get("combined_tax_saving", 0)
        nps_saving = results.get("nps_optimization", {}).get("combined_tax_saving", 0)

        total_annual = hra_saving + sec80c_saving + nps_saving
        monthly = total_annual / 12

        # 10-year invested value (12% return, compounded)
        ten_yr = 0
        monthly_rate = 0.12 / 12
        for m in range(120):
            ten_yr += monthly * ((1 + monthly_rate) ** (120 - m))

        # Score: 0-100 based on utilization of all possible deductions
        max_possible = (150000 * 2 + 50000 * 2 + 200000) * 0.312  # Max savings at 30% bracket
        score = min(100, round(total_annual / max_possible * 100)) if max_possible > 0 else 50

        return {
            "total_annual_tax_saving": round(total_annual),
            "monthly_cash_benefit": round(monthly),
            "ten_year_invested_value": round(ten_yr),
            "optimization_score": score,
            "breakdown": {"hra": round(hra_saving), "section_80c": round(sec80c_saving), "nps": round(nps_saving)},
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 8: LLM NARRATIVE
    # ══════════════════════════════════════════════════════════════════════

    def _generate_couple_plan(self, results: Dict, p1: Dict, p2: Dict) -> str:
        """Generate personalized couple financial plan using Gemini."""
        p1_name, p2_name = p1.get("name", "Partner 1"), p2.get("name", "Partner 2")
        total = results.get("total_optimization", {})
        hra = results.get("hra_optimization", {})
        nps = results.get("nps_optimization", {})
        sip = results.get("sip_allocation", {})
        nw = results.get("net_worth", {})

        rules = ""
        if self.knowledge_base and _HAS_RAG:
            try:
                docs = self.knowledge_base.query("dual income couple tax planning India HRA NPS LTCG")
                rules = "\n".join([d.page_content for d in docs[:3]]) if docs else ""
            except Exception:
                pass
        if not rules:
            rules = ("- Each partner gets separate 80C (₹1.5L), 80CCD1B (₹50K), 80D limits.\n"
                     "- HRA: Only one partner can claim for a given rented property. Choose wisely.\n"
                     "- LTCG: Both get ₹1L exemption each. Split equity investments across both names.\n"
                     "- Joint home loans: Both can claim ₹2L interest each under Sec 24(b) — ₹4L total.")

        prompt = f"""You are a financial planner advising a dual-income Indian couple.
Based on the following computed optimization (numbers pre-calculated — do NOT recalculate), write a personalized plan.
Address both by name: {p1_name} and {p2_name}.

DATA:
- Combined Income: ₹{p1.get('gross_salary',0) + p2.get('gross_salary',0):,.0f}/year
- Total Annual Tax Saving: ₹{total.get('total_annual_tax_saving',0):,.0f}
- Monthly Benefit: ₹{total.get('monthly_cash_benefit',0):,.0f}
- 10-Year Growth (if saved): ₹{total.get('ten_year_invested_value',0):,.0f}
- Optimization Score: {total.get('optimization_score',0)}/100
- HRA: Best scenario = {hra.get('best_scenario','N/A')}
- NPS: Combined monthly needed = ₹{nps.get('combined_monthly_nps',0):,.0f}
- SIPs: {p1_name} ₹{sip.get('p1_total_sip',0):,.0f}/mo, {p2_name} ₹{sip.get('p2_total_sip',0):,.0f}/mo
- Net Worth: ₹{nw.get('net_worth',0):,.0f} ({nw.get('net_worth_pct_of_target',0)}% of FIRE target)

RULES:
{rules}

Cover: 1) Immediate actions this month 2) Tax filing actions (by March 31) 3) Long-term wealth building
Tone: warm, practical, encouraging. Under 500 words. Use ₹."""

        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"LLM couple plan failed: {e}")
            return f"## {p1_name} & {p2_name} — Financial Plan\n\n**Annual saving potential: ₹{total.get('total_annual_tax_saving',0):,.0f}**\n\n### This Month:\n1. Switch HRA to '{hra.get('best_scenario','optimal')}'\n2. Both open NPS Tier-1 (₹{nps.get('combined_monthly_nps',0):,.0f}/mo total)\n3. Start SIPs: {p1_name} ₹{sip.get('p1_total_sip',0):,.0f}/mo, {p2_name} ₹{sip.get('p2_total_sip',0):,.0f}/mo"

    # ══════════════════════════════════════════════════════════════════════
    # CHARTS DATA
    # ══════════════════════════════════════════════════════════════════════

    def _prepare_charts_data(self, results: Dict, p1: Dict, p2: Dict) -> Dict[str, Any]:
        """Prepare Plotly/Streamlit chart data."""
        p1_name, p2_name = p1.get("name", "P1"), p2.get("name", "P2")
        total = results.get("total_optimization", {})
        sip = results.get("sip_allocation", {})
        nw = results.get("net_worth", {})

        return {
            "income_comparison": {"labels": [p1_name, p2_name], "values": [p1.get("gross_salary", 0), p2.get("gross_salary", 0)]},
            "tax_saving_breakdown": total.get("breakdown", {}),
            "sip_split": {"labels": [p1_name, p2_name], "p1": sip.get("p1_total_sip", 0), "p2": sip.get("p2_total_sip", 0)},
            "net_worth_gauge": {"current": nw.get("net_worth", 0), "target": nw.get("retirement_target", 0), "pct": nw.get("net_worth_pct_of_target", 0)},
            "sip_goals": [{"name": g["goal_name"], "p1": g["p1_sip"], "p2": g["p2_sip"]} for g in sip.get("sip_by_goal", [])],
        }

    # ══════════════════════════════════════════════════════════════════════
    # LANGGRAPH NODE INTERFACE
    # ══════════════════════════════════════════════════════════════════════

    def as_langgraph_node(self):
        """Return callable for LangGraph StateGraph.add_node()."""
        def node_fn(state: FinSaarthiState) -> Dict[str, Any]:
            couple = state.get("couple_data", {})
            p1 = couple.get("partner_a_profile", {})
            p2 = couple.get("partner_b_profile", {})
            goals = couple.get("joint_goals", [])

            result = self.optimize(p1, p2, goals)
            opt = result.get("total_optimization", {})

            couple_data: CoupleData = {
                "partner_a_profile": p1, "partner_b_profile": p2,
                "combined_income": p1.get("gross_salary", 0) + p2.get("gross_salary", 0),
                "joint_goals": goals,
                "individual_tax_a": {"best_tax": _fb_best_tax(p1.get("gross_salary",0), p1.get("basic",0), p1.get("hra_received",0), p1.get("rent_paid",0), p1.get("city","metro"), p1.get("deductions_80c",0), p1.get("deductions_80d",0), p1.get("nps_existing",0), 0)},
                "individual_tax_b": {"best_tax": _fb_best_tax(p2.get("gross_salary",0), p2.get("basic",0), p2.get("hra_received",0), p2.get("rent_paid",0), p2.get("city","metro"), p2.get("deductions_80c",0), p2.get("deductions_80d",0), p2.get("nps_existing",0), 0)},
                "optimized_tax_split": result.get("section_80c_optimization", {}),
                "joint_sip_plan": result.get("sip_allocation", {}).get("sip_by_goal", []),
                "joint_fire_number": result.get("net_worth", {}).get("retirement_target", 0),
                "savings_vs_separate": opt.get("total_annual_tax_saving", 0),
            }
            return {"couple_data": couple_data, "agent_results": result,
                    "final_response": result.get("narrative", ""), "error_message": result.get("error_message", "")}
        return node_fn
