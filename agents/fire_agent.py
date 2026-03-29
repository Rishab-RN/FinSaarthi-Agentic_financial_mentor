"""
FinSaarthi — FIRE Path Planner Agent (Module 2)
=================================================
Generates a complete Financial Independence roadmap: FIRE number,
goal-wise SIP decomposition, monthly roadmap, insurance check,
and LLM-powered narrative advice.

Rule: ALL math in Python. LLM only for natural language explanation.

File: agents/fire_agent.py
Branch: feature/agents
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from state import FinSaarthiState, FIREData
from tools.audit_logger import AuditLogger

try:
    from tools.financial_calc import calculate_sip_for_goal, calculate_fire_number
    _HAS_CALC = True
except ImportError:
    _HAS_CALC = False

try:
    from rag.knowledge_base import FinancialKnowledgeBase
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False

logger = logging.getLogger("finsaarthi.fire_agent")

# ── Fallback math (used before tools branch merges) ──────────────────────────

def _fb_sip_for_goal(goal_today: float, years: int, ret: float, inf: float, savings: float = 0) -> Dict[str, float]:
    """Fallback SIP calculator using basic FV/PMT formulas."""
    future_goal = goal_today * ((1 + inf) ** years)
    fv_savings = savings * ((1 + ret) ** years)
    shortfall = max(0, future_goal - fv_savings)
    if shortfall <= 0:
        return {"monthly_sip": 0, "future_goal_value": future_goal, "real_return_rate": (1+ret)/(1+inf)-1, "total_investment": savings, "total_returns": fv_savings - savings}
    monthly_rate = ret / 12
    n = years * 12
    # SIP FV formula inverted: SIP = FV * r / ((1+r)^n - 1)
    if monthly_rate > 0:
        sip = shortfall * monthly_rate / (((1 + monthly_rate) ** n) - 1)
    else:
        sip = shortfall / n
    total_inv = savings + sip * n
    return {"monthly_sip": round(sip, 0), "future_goal_value": round(future_goal, 0), "real_return_rate": round((1+ret)/(1+inf)-1, 4), "total_investment": round(total_inv, 0), "total_returns": round(future_goal - total_inv, 0)}

def _fb_fire_number(monthly_exp: float, inflation: float = 0.06, swr: float = 0.04) -> Dict[str, float]:
    """Fallback FIRE corpus calculator."""
    annual = monthly_exp * 12
    corpus = annual / swr
    return {"fire_corpus": round(corpus, 0), "monthly_passive_income_at_retirement": round(corpus * swr / 12, 0), "years_of_runway": int(1 / swr)}

# ── Return rate assumptions by fund category ─────────────────────────────────
CATEGORY_RETURNS = {
    "Large Cap Equity": 0.12, "Mid Cap Equity": 0.14, "Small Cap Equity": 0.16,
    "Flexi Cap Equity": 0.13, "International Equity": 0.11, "Hybrid Aggressive": 0.10,
    "Hybrid Conservative": 0.08, "Debt Short Duration": 0.07, "Debt Liquid": 0.06, "Gold": 0.08,
}


class FIREAgent:
    """
    Module 2: FIRE Path Planner Agent.

    Pipeline: FIRE number → Goal decomposition → SIP feasibility →
              Insurance check → Monthly roadmap → Asset allocation →
              LLM narrative.

    Parameters:
        llm: LangChain-compatible LLM (Gemini 1.5 Pro).
        knowledge_base: RAG knowledge base for financial rules.
        audit_logger (AuditLogger): SQLite audit trail.
    """

    AGENT_NAME: str = "fire_agent"

    def __init__(self, llm: Any, knowledge_base: Any = None, audit_logger: Optional[AuditLogger] = None) -> None:
        self.llm = llm
        self.knowledge_base = knowledge_base
        self.audit_logger = audit_logger or AuditLogger()
        logger.info("FIREAgent initialized.")

    # ══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════

    def plan(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the complete FIRE planning pipeline.

        Parameters:
            user_data (dict): Keys: age, monthly_income, monthly_expenses,
                existing_investments (dict), goals (list), risk_profile,
                target_retirement_age, existing_life_cover, existing_health_cover,
                existing_emis.

        Returns:
            Dict with fire_number, goals_breakdown, sip_feasibility,
            insurance_check, monthly_roadmap, asset_allocation, narrative, charts_data.
        """
        start = time.perf_counter()
        results: Dict[str, Any] = {}

        self.audit_logger.log(self.AGENT_NAME, "plan_started", input_summary=f"Age:{user_data.get('age')}, Income:₹{user_data.get('monthly_income',0):,.0f}/mo")

        try:
            # Step 1: FIRE Number
            with self.audit_logger.track(self.AGENT_NAME, "calculate_fire_number") as t:
                fire = self._calculate_fire_number(user_data)
                t.set_output(f"FIRE corpus: ₹{fire['fire_corpus']:,.0f}")
                t.set_tools(["fire_math"])
            results["fire_number"] = fire

            # Step 2: Goal Decomposition
            with self.audit_logger.track(self.AGENT_NAME, "decompose_goals") as t:
                goals = self._decompose_goals(user_data.get("goals", []), user_data)
                t.set_output(f"Decomposed {len(goals)} goals incl. retirement")
                t.set_tools(["sip_calculator", "inflation_adjuster"])
            results["goals_breakdown"] = goals

            # Step 3: SIP Feasibility
            with self.audit_logger.track(self.AGENT_NAME, "calculate_sip_feasibility") as t:
                sip = self._calculate_total_sip(goals, user_data.get("monthly_income", 0), user_data.get("monthly_expenses", 0), user_data.get("existing_emis", 0))
                t.set_output(f"Total SIP: ₹{sip['total_sip_needed']:,.0f}/mo, Gap: ₹{sip['sip_gap']:,.0f}")
                t.set_tools(["sip_aggregator"])
            results["sip_feasibility"] = sip

            # Step 4: Insurance
            with self.audit_logger.track(self.AGENT_NAME, "check_insurance") as t:
                insurance = self._check_insurance_adequacy(user_data)
                t.set_output(f"Life gap: ₹{insurance['life_cover_gap']:,.0f}, Health gap: ₹{insurance['health_cover_gap']:,.0f}")
                t.set_tools(["insurance_rules"])
            results["insurance_check"] = insurance

            # Step 5: Monthly Roadmap
            with self.audit_logger.track(self.AGENT_NAME, "build_roadmap") as t:
                roadmap = self._build_monthly_roadmap(goals, user_data)
                t.set_output(f"Generated {len(roadmap)} milestone entries")
                t.set_tools(["roadmap_builder"])
            results["monthly_roadmap"] = roadmap

            # Step 6: Asset Allocation
            with self.audit_logger.track(self.AGENT_NAME, "asset_allocation") as t:
                allocation = self._asset_allocation_recommendation(user_data.get("age", 30), user_data.get("risk_profile", "moderate"))
                t.set_output(f"Equity: {allocation['equity_pct']}%, Debt: {allocation['debt_pct']}%")
                t.set_tools(["age_rule"])
            results["asset_allocation"] = allocation

            # Step 7: Year-wise corpus projection
            with self.audit_logger.track(self.AGENT_NAME, "corpus_projection") as t:
                projection = self._year_wise_projection(user_data, sip, allocation)
                t.set_output(f"Projected {len(projection)} years")
                t.set_tools(["compounding_math"])
            results["year_wise_projection"] = projection

            # Step 8: LLM Narrative
            with self.audit_logger.track(self.AGENT_NAME, "generate_narrative") as t:
                narrative = self._generate_narrative(results, user_data)
                t.set_output(f"Generated {len(narrative.split())}-word narrative")
                t.set_tools(["gemini-1.5-pro", "rag"])
            results["narrative"] = narrative

            # Step 9: Charts data
            results["charts_data"] = self._prepare_charts_data(results)

        except Exception as e:
            logger.error(traceback.format_exc())
            self.audit_logger.log(self.AGENT_NAME, "plan_failed", status="error", error_detail=str(e))
            results["error_message"] = str(e)

        elapsed = int((time.perf_counter() - start) * 1000)
        self.audit_logger.log(self.AGENT_NAME, "plan_completed", output_summary=f"Completed in {elapsed}ms", duration_ms=elapsed)
        return results

    # ══════════════════════════════════════════════════════════════════════
    # STEP 1: FIRE NUMBER
    # ══════════════════════════════════════════════════════════════════════

    def _calculate_fire_number(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate FIRE corpus adjusting current expenses for inflation
        to the retirement year.

        Parameters:
            user_data (dict): Must contain monthly_expenses, age, target_retirement_age.

        Returns:
            Dict: fire_corpus, monthly_retirement_expense, years_to_build, current_shortfall.
        """
        age = user_data.get("age", 30)
        retire_age = user_data.get("target_retirement_age", 50)
        monthly_exp = user_data.get("monthly_expenses", 50000)
        inflation = user_data.get("inflation_rate", 0.06)
        swr = 0.04  # 4% safe withdrawal rate

        years_to_retire = max(retire_age - age, 1)

        # Inflate current expenses to retirement year
        monthly_retirement_expense = monthly_exp * ((1 + inflation) ** years_to_retire)

        fire_func = calculate_fire_number if _HAS_CALC else _fb_fire_number
        fire_result = fire_func(monthly_retirement_expense, inflation, swr)

        existing = sum(user_data.get("existing_investments", {}).values()) if isinstance(user_data.get("existing_investments"), dict) else user_data.get("existing_investments", 0)
        shortfall = max(0, fire_result["fire_corpus"] - existing)

        return {
            "fire_corpus": fire_result["fire_corpus"],
            "monthly_retirement_expense": round(monthly_retirement_expense, 0),
            "years_to_build": years_to_retire,
            "current_shortfall": round(shortfall, 0),
            "existing_corpus": round(existing, 0),
            "safe_withdrawal_rate": swr,
            "inflation_rate": inflation,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 2: GOAL DECOMPOSITION
    # ══════════════════════════════════════════════════════════════════════

    def _decompose_goals(self, goals: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decompose each financial goal into actionable SIP targets.

        Automatically adds retirement as the final goal using _calculate_fire_number.
        Assigns optimal fund category based on time horizon.

        Parameters:
            goals (list): Each dict has name, amount_today, years.
            user_data (dict): User profile for retirement calc.

        Returns:
            List of dicts with goal_name, amount_today, future_value, years,
            monthly_sip_needed, fund_category, priority, expected_return.
        """
        sip_func = calculate_sip_for_goal if _HAS_CALC else _fb_sip_for_goal
        inflation = user_data.get("inflation_rate", 0.06)
        decomposed: List[Dict[str, Any]] = []

        for i, goal in enumerate(goals):
            name = goal.get("name", f"Goal {i+1}")
            amount_today = goal.get("amount_today", 0)
            years = goal.get("years", 5)
            existing_for_goal = goal.get("existing_savings", 0)

            # Choose fund category by time horizon
            if years >= 7:
                category = "Mid Cap Equity"
                priority = "long-term"
            elif years >= 5:
                category = "Large Cap Equity"
                priority = "medium-term"
            elif years >= 3:
                category = "Hybrid Aggressive"
                priority = "medium-term"
            else:
                category = "Debt Short Duration"
                priority = "short-term"

            expected_return = CATEGORY_RETURNS.get(category, 0.12)
            sip_result = sip_func(amount_today, years, expected_return, inflation, existing_for_goal)

            decomposed.append({
                "goal_name": name,
                "amount_today": amount_today,
                "future_value": sip_result["future_goal_value"],
                "years": years,
                "monthly_sip_needed": sip_result["monthly_sip"],
                "fund_category": category,
                "expected_return": expected_return,
                "priority": priority,
                "total_investment": sip_result["total_investment"],
                "total_returns": sip_result["total_returns"],
            })

        # Add retirement goal automatically
        fire = self._calculate_fire_number(user_data)
        retire_years = fire["years_to_build"]
        retire_category = "Flexi Cap Equity" if retire_years >= 10 else "Large Cap Equity"
        retire_return = CATEGORY_RETURNS.get(retire_category, 0.12)
        retire_sip = sip_func(fire["fire_corpus"] / ((1 + inflation) ** retire_years), retire_years, retire_return, inflation, fire["existing_corpus"])

        decomposed.append({
            "goal_name": "🔥 Retirement (FIRE)",
            "amount_today": round(fire["fire_corpus"] / ((1 + inflation) ** retire_years), 0),
            "future_value": fire["fire_corpus"],
            "years": retire_years,
            "monthly_sip_needed": retire_sip["monthly_sip"],
            "fund_category": retire_category,
            "expected_return": retire_return,
            "priority": "critical",
            "total_investment": retire_sip["total_investment"],
            "total_returns": retire_sip["total_returns"],
        })

        # Sort: critical first, then by years ascending
        priority_order = {"critical": 0, "short-term": 1, "medium-term": 2, "long-term": 3}
        decomposed.sort(key=lambda g: (priority_order.get(g["priority"], 9), g["years"]))

        return decomposed

    # ══════════════════════════════════════════════════════════════════════
    # STEP 3: SIP FEASIBILITY
    # ══════════════════════════════════════════════════════════════════════

    def _calculate_total_sip(self, goals: List[Dict[str, Any]], monthly_income: float, monthly_expenses: float, existing_emis: float = 0) -> Dict[str, Any]:
        """
        Check if the total SIP requirement is feasible given the user's income.

        Parameters:
            goals: Decomposed goals with monthly_sip_needed.
            monthly_income: Gross monthly income.
            monthly_expenses: Monthly living expenses.
            existing_emis: Existing EMI obligations.

        Returns:
            Dict with total_sip_needed, investable_surplus, sip_gap, is_feasible, suggestions.
        """
        total_sip = sum(g["monthly_sip_needed"] for g in goals)
        investable_surplus = monthly_income - monthly_expenses - existing_emis
        sip_gap = max(0, total_sip - investable_surplus)
        is_feasible = sip_gap <= 0

        suggestions: List[str] = []
        if not is_feasible:
            gap_pct = (sip_gap / monthly_income * 100) if monthly_income > 0 else 0

            if gap_pct < 10:
                suggestions.append(f"Reduce discretionary expenses by ₹{sip_gap:,.0f}/month ({gap_pct:.1f}% of income) to close the gap.")
            elif gap_pct < 25:
                suggestions.append(f"Consider extending your shortest-term goal by 2-3 years to reduce monthly SIP by ~30%.")
                suggestions.append(f"Target a monthly expense reduction of ₹{sip_gap * 0.5:,.0f} and increase income by ₹{sip_gap * 0.5:,.0f}.")
            else:
                suggestions.append("Your goals may be too aggressive for current income. Consider prioritizing top 2-3 goals.")
                suggestions.append(f"You need ₹{sip_gap:,.0f}/month more. Focus on career growth to increase income by {gap_pct:.0f}%.")

            suggestions.append("Start with whatever SIP you can afford NOW — even ₹500/month. Increase with every salary hike.")
            suggestions.append("Apply the 50-30-20 rule: 50% needs, 30% wants, 20% investments.")

        savings_rate = ((investable_surplus / monthly_income) * 100) if monthly_income > 0 else 0

        return {
            "total_sip_needed": round(total_sip, 0),
            "investable_surplus": round(investable_surplus, 0),
            "sip_gap": round(sip_gap, 0),
            "is_feasible": is_feasible,
            "savings_rate_pct": round(savings_rate, 1),
            "suggestions": suggestions,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 4: INSURANCE CHECK
    # ══════════════════════════════════════════════════════════════════════

    def _check_insurance_adequacy(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if life and health insurance coverage is adequate.

        Rules:
            Life cover = annual_income × 10 (IRDA guideline)
            Health cover = ₹10L individual / ₹25L family minimum

        Parameters:
            user_data (dict): With monthly_income, existing_life_cover, existing_health_cover, has_dependents.

        Returns:
            Dict with cover needs, gaps, and premium estimates.
        """
        annual_income = user_data.get("monthly_income", 0) * 12
        has_dependents = user_data.get("has_dependents", True)

        life_needed = annual_income * 10
        life_existing = user_data.get("existing_life_cover", 0)
        life_gap = max(0, life_needed - life_existing)

        health_needed = 2500000 if has_dependents else 1000000
        health_existing = user_data.get("existing_health_cover", 0)
        health_gap = max(0, health_needed - health_existing)

        # Premium estimates (rough — ₹5-8 per lakh for term, ₹800-1200/lakh for health)
        age = user_data.get("age", 30)
        term_rate = 6 if age < 35 else 10 if age < 45 else 18  # per lakh per year
        health_rate = 900 if age < 35 else 1200 if age < 45 else 1800

        life_premium_annual = (life_gap / 100000) * term_rate if life_gap > 0 else 0
        health_premium_annual = (health_gap / 100000) * health_rate if health_gap > 0 else 0
        monthly_premium = (life_premium_annual + health_premium_annual) / 12

        alerts: List[str] = []
        if life_gap > 0:
            alerts.append(f"⚠️ Life cover gap: ₹{life_gap / 100000:.0f}L. Get a pure term plan BEFORE starting SIPs.")
        if health_gap > 0:
            alerts.append(f"⚠️ Health cover gap: ₹{health_gap / 100000:.0f}L. One medical emergency can wipe out years of savings.")
        if not alerts:
            alerts.append("✅ Insurance coverage is adequate. Well done!")

        return {
            "life_cover_needed": round(life_needed, 0),
            "life_cover_existing": round(life_existing, 0),
            "life_cover_gap": round(life_gap, 0),
            "health_cover_needed": round(health_needed, 0),
            "health_cover_existing": round(health_existing, 0),
            "health_cover_gap": round(health_gap, 0),
            "monthly_premium_estimate": round(monthly_premium, 0),
            "alerts": alerts,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STEP 5: MONTHLY ROADMAP
    # ══════════════════════════════════════════════════════════════════════

    def _build_monthly_roadmap(self, goals: List[Dict[str, Any]], user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate milestone-based roadmap entries.

        Parameters:
            goals: Decomposed goals list.
            user_data: User profile.

        Returns:
            List of milestone dicts: month, year, action, amount, running_corpus_estimate.
        """
        total_sip = sum(g["monthly_sip_needed"] for g in goals)
        avg_return_monthly = 0.12 / 12  # 12% annualized
        existing = sum(user_data.get("existing_investments", {}).values()) if isinstance(user_data.get("existing_investments"), dict) else user_data.get("existing_investments", 0)

        roadmap: List[Dict[str, Any]] = []
        corpus = existing

        # Month 1: Start
        roadmap.append({"month": 1, "year": 1, "action": "🚀 Start all SIPs + buy term insurance", "amount": total_sip, "running_corpus_estimate": round(corpus + total_sip, 0)})

        # Month 3: Emergency fund check
        roadmap.append({"month": 3, "year": 1, "action": "🏦 Verify 6-month emergency fund in liquid fund", "amount": user_data.get("monthly_expenses", 50000) * 6, "running_corpus_estimate": round(corpus + total_sip * 3, 0)})

        # Month 6: First review
        corpus_m6 = existing * ((1 + avg_return_monthly) ** 6) + total_sip * sum((1 + avg_return_monthly) ** i for i in range(6))
        roadmap.append({"month": 6, "year": 1, "action": "📊 First portfolio review — check fund performance", "amount": total_sip, "running_corpus_estimate": round(corpus_m6, 0)})

        # Year 1: Step-up
        corpus_y1 = existing * ((1 + avg_return_monthly) ** 12) + total_sip * sum((1 + avg_return_monthly) ** i for i in range(12))
        stepped_sip = round(total_sip * 1.10, 0)
        roadmap.append({"month": 12, "year": 1, "action": "⬆️ Step-up SIP by 10% (₹{:,.0f} → ₹{:,.0f})".format(total_sip, stepped_sip), "amount": stepped_sip, "running_corpus_estimate": round(corpus_y1, 0)})

        # Goal achievement milestones
        for goal in goals:
            goal_month = goal["years"] * 12
            if goal_month > 12:
                # Rough corpus at that point
                corpus_at_goal = existing * ((1 + avg_return_monthly) ** goal_month) + total_sip * sum((1 + avg_return_monthly) ** i for i in range(min(goal_month, 360)))
                roadmap.append({
                    "month": goal_month,
                    "year": goal["years"],
                    "action": f"🎯 Goal achieved: {goal['goal_name']} (₹{goal['future_value']:,.0f})",
                    "amount": goal["future_value"],
                    "running_corpus_estimate": round(corpus_at_goal, 0),
                })

        # Every 5 years: rebalance
        max_years = max(g["years"] for g in goals) if goals else 20
        for yr in range(5, max_years + 1, 5):
            already_has = any(r["year"] == yr for r in roadmap)
            if not already_has:
                roadmap.append({"month": yr * 12, "year": yr, "action": "🔄 Rebalance — shift equity to debt as goals approach", "amount": 0, "running_corpus_estimate": 0})

        roadmap.sort(key=lambda r: r["month"])
        return roadmap

    # ══════════════════════════════════════════════════════════════════════
    # STEP 6: ASSET ALLOCATION
    # ══════════════════════════════════════════════════════════════════════

    def _asset_allocation_recommendation(self, age: int, risk_profile: str) -> Dict[str, Any]:
        """
        Age-based + risk-profile asset allocation.

        Parameters:
            age: Current age.
            risk_profile: "conservative", "moderate", or "aggressive".

        Returns:
            Dict with equity_pct, debt_pct, gold_pct, breakdown_by_category.
        """
        base = {"conservative": 100, "moderate": 110, "aggressive": 120}.get(risk_profile, 110)
        equity_pct = min(max(base - age, 20), 90)  # Clamp 20-90%
        debt_pct = max(100 - equity_pct - 5, 5)     # At least 5% debt
        gold_pct = 5  # Fixed 5% tactical gold

        # Normalize to 100%
        total = equity_pct + debt_pct + gold_pct
        equity_pct = round(equity_pct / total * 100)
        debt_pct = round(debt_pct / total * 100)
        gold_pct = 100 - equity_pct - debt_pct

        # Sub-breakdown of equity
        if risk_profile == "aggressive":
            breakdown = {"Large Cap": round(equity_pct * 0.30), "Mid Cap": round(equity_pct * 0.25), "Small Cap": round(equity_pct * 0.20), "International": round(equity_pct * 0.10), "Flexi Cap": round(equity_pct * 0.15), "Debt": debt_pct, "Gold": gold_pct}
        elif risk_profile == "conservative":
            breakdown = {"Large Cap": round(equity_pct * 0.50), "Mid Cap": round(equity_pct * 0.15), "Small Cap": round(equity_pct * 0.05), "International": round(equity_pct * 0.10), "Flexi Cap": round(equity_pct * 0.20), "Debt": debt_pct, "Gold": gold_pct}
        else:
            breakdown = {"Large Cap": round(equity_pct * 0.40), "Mid Cap": round(equity_pct * 0.20), "Small Cap": round(equity_pct * 0.10), "International": round(equity_pct * 0.10), "Flexi Cap": round(equity_pct * 0.20), "Debt": debt_pct, "Gold": gold_pct}

        return {"equity_pct": equity_pct, "debt_pct": debt_pct, "gold_pct": gold_pct, "breakdown_by_category": breakdown}

    # ══════════════════════════════════════════════════════════════════════
    # STEP 7: YEAR-WISE PROJECTION
    # ══════════════════════════════════════════════════════════════════════

    def _year_wise_projection(self, user_data: Dict[str, Any], sip_data: Dict[str, Any], allocation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Project corpus growth year-by-year with 10% annual SIP step-up.

        Parameters:
            user_data: User profile.
            sip_data: SIP feasibility results.
            allocation: Asset allocation.

        Returns:
            List of yearly snapshots: year, age, annual_sip, corpus, fire_pct.
        """
        age = user_data.get("age", 30)
        retire_age = user_data.get("target_retirement_age", 50)
        years = retire_age - age
        monthly_sip = min(sip_data["total_sip_needed"], sip_data["investable_surplus"])  # realistic SIP
        existing = sum(user_data.get("existing_investments", {}).values()) if isinstance(user_data.get("existing_investments"), dict) else user_data.get("existing_investments", 0)

        weighted_return = (allocation["equity_pct"] / 100 * 0.12) + (allocation["debt_pct"] / 100 * 0.07) + (allocation["gold_pct"] / 100 * 0.08)
        fire_corpus = self._calculate_fire_number(user_data)["fire_corpus"]

        projection: List[Dict[str, Any]] = []
        corpus = existing

        for yr in range(1, years + 1):
            annual_sip = monthly_sip * 12
            corpus = corpus * (1 + weighted_return) + annual_sip
            fire_pct = min(round(corpus / fire_corpus * 100, 1), 100) if fire_corpus > 0 else 0

            projection.append({
                "year": yr, "age": age + yr, "annual_sip": round(annual_sip, 0),
                "corpus": round(corpus, 0), "fire_pct": fire_pct,
            })

            monthly_sip *= 1.10  # 10% annual step-up

        return projection

    # ══════════════════════════════════════════════════════════════════════
    # STEP 8: LLM NARRATIVE
    # ══════════════════════════════════════════════════════════════════════

    def _generate_narrative(self, plan_data: Dict[str, Any], user_data: Dict[str, Any]) -> str:
        """
        Generate personalized, encouraging financial plan narrative using Gemini.

        Parameters:
            plan_data: Complete plan results.
            user_data: User profile.

        Returns:
            str: Markdown narrative text.
        """
        fire = plan_data.get("fire_number", {})
        sip = plan_data.get("sip_feasibility", {})
        goals = plan_data.get("goals_breakdown", [])
        insurance = plan_data.get("insurance_check", {})

        goals_summary = "\n".join([f"- {g['goal_name']}: ₹{g['monthly_sip_needed']:,.0f}/mo for {g['years']}yrs → ₹{g['future_value']:,.0f}" for g in goals])

        # RAG retrieval
        rules = ""
        if self.knowledge_base and _HAS_RAG:
            try:
                docs = self.knowledge_base.query("SIP step-up benefits inflation impact FIRE planning India")
                rules = "\n".join([d.page_content for d in docs[:3]]) if docs else ""
            except Exception:
                rules = ""
        if not rules:
            rules = ("- Step-up SIP by 10% annually to beat inflation.\n"
                     "- 4% safe withdrawal rate is the global FIRE standard.\n"
                     "- Term insurance before investments — always.\n"
                     "- Emergency fund = 6 months expenses in liquid fund.")

        prompt = f"""You are a SEBI-registered financial planner. Explain the following financial plan to a {user_data.get('age', 28)}-year-old Indian professional in simple, encouraging language. Highlight the most important 3 actions they must take THIS MONTH.

DATA:
- FIRE Corpus Needed: ₹{fire.get('fire_corpus', 0):,.0f}
- Years to FIRE: {fire.get('years_to_build', 20)}
- Monthly Retirement Expense: ₹{fire.get('monthly_retirement_expense', 0):,.0f}
- Total SIP Needed: ₹{sip.get('total_sip_needed', 0):,.0f}/month
- Investable Surplus: ₹{sip.get('investable_surplus', 0):,.0f}/month
- SIP Feasible: {'Yes ✅' if sip.get('is_feasible') else 'No ❌ (Gap: ₹' + f"{sip.get('sip_gap', 0):,.0f}" + ')'}
- Insurance Alerts: {'; '.join(insurance.get('alerts', []))}

GOALS:
{goals_summary}

RELEVANT RULES:
{rules}

Keep response under 300 words. Do NOT suggest specific fund names. Use ₹ for amounts."""

        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"LLM narrative failed: {e}")
            return self._fallback_narrative(plan_data, user_data)

    def _fallback_narrative(self, plan_data: Dict[str, Any], user_data: Dict[str, Any]) -> str:
        """Rule-based narrative when LLM is unavailable."""
        fire = plan_data.get("fire_number", {})
        sip = plan_data.get("sip_feasibility", {})
        age = user_data.get("age", 30)

        return f"""## Your FIRE Roadmap Summary

You're {age} years old with {fire.get('years_to_build', 20)} years to financial independence. Your target FIRE corpus is **₹{fire.get('fire_corpus', 0):,.0f}**.

### 3 Actions This Month:
1. **Start SIPs** worth ₹{sip.get('total_sip_needed', 0):,.0f}/month across your goal-mapped funds
2. **Buy term insurance** if you have any life cover gap
3. **Set up 6-month emergency fund** in a liquid fund before aggressive investing

{'⚠️ Your current surplus (₹' + f"{sip.get('investable_surplus', 0):,.0f}" + ') is less than the SIP needed. Start with what you can, and increase with every salary hike.' if not sip.get('is_feasible') else '✅ Your income comfortably supports your goals. Stay disciplined!'}

*Step up your SIP by 10% every year to stay ahead of inflation.*"""

    # ══════════════════════════════════════════════════════════════════════
    # CHARTS DATA
    # ══════════════════════════════════════════════════════════════════════

    def _prepare_charts_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare Plotly/Streamlit chart data structures."""
        projection = results.get("year_wise_projection", [])
        goals = results.get("goals_breakdown", [])
        allocation = results.get("asset_allocation", {})

        return {
            "corpus_projection": {"years": [p["year"] for p in projection], "corpus": [p["corpus"] for p in projection], "fire_pct": [p["fire_pct"] for p in projection]},
            "goals_sip_bar": {"names": [g["goal_name"] for g in goals], "sips": [g["monthly_sip_needed"] for g in goals], "categories": [g["fund_category"] for g in goals]},
            "allocation_pie": allocation.get("breakdown_by_category", {}),
            "fire_progress_gauge": results.get("year_wise_projection", [{}])[-1].get("fire_pct", 0) if projection else 0,
        }

    # ══════════════════════════════════════════════════════════════════════
    # LANGGRAPH NODE INTERFACE
    # ══════════════════════════════════════════════════════════════════════

    def as_langgraph_node(self):
        """Return a callable for LangGraph StateGraph.add_node()."""

        def node_fn(state: FinSaarthiState) -> Dict[str, Any]:
            profile = state.get("user_profile", {})
            user_data = {
                "age": profile.get("age", 30),
                "monthly_income": profile.get("annual_income", 0) / 12,
                "monthly_expenses": profile.get("monthly_expenses", 0),
                "existing_investments": profile.get("existing_investments", 0),
                "risk_profile": profile.get("risk_tolerance", "moderate"),
                "target_retirement_age": 50,
                "goals": state.get("fire_data", {}).get("goal_breakdown", []),
                "existing_life_cover": 0,
                "existing_health_cover": 0,
                "existing_emis": 0,
            }
            plan = self.plan(user_data)

            fire_data: FIREData = {
                "current_age": user_data["age"],
                "target_retirement_age": user_data["target_retirement_age"],
                "monthly_income": user_data["monthly_income"],
                "monthly_expenses": user_data["monthly_expenses"],
                "fire_number": plan.get("fire_number", {}).get("fire_corpus", 0),
                "monthly_sip_required": plan.get("sip_feasibility", {}).get("total_sip_needed", 0),
                "year_wise_projection": plan.get("year_wise_projection", []),
                "goal_breakdown": plan.get("goals_breakdown", []),
                "sip_roadmap": plan.get("monthly_roadmap", []),
            }

            return {"fire_data": fire_data, "agent_results": plan, "final_response": plan.get("narrative", ""), "error_message": plan.get("error_message", "")}

        return node_fn
