"""
FinSaarthi — Financial Mathematical Core
=========================================
Analytical engine for all calculations including XIRR, Tax, FIRE, and Portfolio Overlap.
As per M2 requirements: ALL numbers come from here, never from the LLM.

File: tools/financial_calc.py
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import numpy_financial as npf
import pandas as pd
from scipy.optimize import brentq

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("financial_calc")


class FinancialCalculator:
    """
    Core mathematical engine for FinSaarthi, optimized for Indian financial contexts.
    """

    # 1. --- XIRR CALCULATION (Using Brentq) ---

    @staticmethod
    def calculate_xirr(cashflows: List[float], dates: List[date]) -> float:
        """
        Calculate annualized XIRR using Brent's method.
        
        Args:
            cashflows: List of signed amounts (negative=investment, positive=current/out).
            dates: Corresponding transaction dates.
            
        Returns:
            float: Annualized XIRR as a decimal (0.1415 = 14.15%).
        """
        if len(cashflows) != len(dates) or len(cashflows) < 2:
            return 0.0

        # Ensure we have at least one negative and one positive value
        if all(c >= 0 for c in cashflows) or all(c <= 0 for c in cashflows):
            return 0.0

        def xnpv(rate: float) -> float:
            """Internal XNPV function: NPV = sum(C_i / (1+r)^((d_i - d_0)/365))"""
            d0 = dates[0]
            total = 0.0
            for c, d in zip(cashflows, dates):
                days = (d - d0).days
                total += c / ((1 + rate) ** (days / 365.0))
            return total

        try:
            # Brent's method requires a bracket [a, b] where f(a) and f(b) have opposite signs
            # We'll search between -0.999 (near death return) and 100 (10,000% return)
            return brentq(xnpv, -0.999, 100, xtol=1e-6)
        except (ValueError, RuntimeError) as e:
            logger.error(f"XIRR non-convergence: {e}")
            return 0.0

    # 2. --- SIP FOR GOAL ---

    @staticmethod
    def calculate_sip_for_goal(
        goal_amount_today: float,
        years: int,
        expected_return: float,
        inflation: float,
        current_savings: float = 0
    ) -> Dict[str, Any]:
        """
        Calculate required monthly SIP to meet a future goal, adjusted for inflation.
        """
        # Adjusted returns calculation: real_return = (1+nominal)/(1+inflation) - 1
        r_nom = expected_return / 100.0
        i_inf = inflation / 100.0
        real_return_rate = ((1 + r_nom) / (1 + i_inf)) - 1

        # Real future value is calculated in today's currency then adjusted
        # But usually we inflate the target amount: 
        future_goal_value = goal_amount_today * ((1 + i_inf) ** years)
        
        # Calculate monthly SIP needed to reach future_goal_value starting with current_savings
        # pmt(rate, nper, pv, fv)
        monthly_rate = r_nom / 12
        months = years * 12
        
        # We need PMT to reach -future_goal_value (FV is negative in npf.pmt context)
        # Or more simply: 
        fv_of_lumpsum = current_savings * ((1 + r_nom) ** years)
        gap = future_goal_value - fv_of_lumpsum
        
        if gap <= 0:
            monthly_sip = 0.0
        else:
            monthly_sip = npf.pmt(monthly_rate, months, 0, -gap)

        total_investment = (monthly_sip * months) + current_savings
        total_returns = future_goal_value - total_investment

        return {
            "monthly_sip": round(float(monthly_sip), 2),
            "future_goal_value": round(future_goal_value, 2),
            "real_return_rate": round(real_return_rate * 100, 2),
            "total_investment": round(total_investment, 2),
            "total_returns": round(total_returns, 2)
        }

    # 3. --- PORTFOLIO OVERLAP (Jaccard Similarity) ---

    @staticmethod
    def calculate_portfolio_overlap(fund_holdings: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Calculate stock overlap between mutual funds using Jaccard Similarity.
        """
        funds = list(fund_holdings.keys())
        matrix = {}
        highest_overlap = 0.0
        overlap_pair = ("None", "None")

        for i in range(len(funds)):
            f1 = funds[i]
            matrix[f1] = {}
            for j in range(len(funds)):
                f2 = funds[j]
                if f1 == f2:
                    matrix[f1][f2] = 100.0
                    continue
                
                s1 = set(fund_holdings[f1])
                s2 = set(fund_holdings[f2])
                
                intersection = len(s1.intersection(s2))
                union = len(s1.union(s2))
                
                jaccard = (intersection / union) if union > 0 else 0
                percentage = round(jaccard * 100, 2)
                matrix[f1][f2] = percentage

                if i < j and percentage > highest_overlap:
                    highest_overlap = percentage
                    overlap_pair = (f1, f2)

        recommendation = "Maintain holdings — diversification is healthy."
        if highest_overlap > 50:
            recommendation = f"Critical Overlap: {overlap_pair[0]} and {overlap_pair[1]} share over 50% stocks. Consider switching one to a different category."
        elif highest_overlap > 30:
            recommendation = f"Moderate Overlap between {overlap_pair[0]} and {overlap_pair[1]}. Monitor for concentration risk."

        return {
            "overlap_matrix": matrix,
            "highest_overlap": highest_overlap,
            "highest_overlap_pair": overlap_pair,
            "recommendation": recommendation
        }

    # 4. --- EXPENSE DRAG ---

    @staticmethod
    def calculate_expense_drag(portfolio: List[Dict[str, Any]], years: int = 10) -> Dict[str, Any]:
        """
        Calculate compounding cost of Expense Ratios over N years.
        """
        annual_fees_total = 0.0
        total_value = 0.0
        drag_results = []
        
        # Nominal return assumption for drag calculation (e.g., 12%)
        r = 0.12

        for item in portfolio:
            val = item['current_value']
            er = item['expense_ratio'] / 100.0
            total_value += val
            
            annual_fee = val * er
            annual_fees_total += annual_fee
            
            # Future Value with and without fees
            fv_no_fees = val * ((1 + r) ** years)
            fv_with_fees = val * ((1 + (r - er)) ** years)
            drag = fv_no_fees - fv_with_fees
            
            drag_results.append({
                "fund_name": item['fund_name'],
                "drag": drag,
                "expense_ratio": item['expense_ratio']
            })

        # Find worst fund (highest expense ratio)
        worst_fund = max(drag_results, key=lambda x: x['expense_ratio']) if drag_results else None
        
        # Total drag sum
        ten_year_drag = sum(d['drag'] for d in drag_results)
        
        # Savings if switched to a low-cost index (e.g., 0.1% ER)
        target_er = 0.001
        fv_optimized = total_value * ((1 + (r - target_er)) ** years)
        fv_current = sum(item['current_value'] * ((1 + (r - (item['expense_ratio']/100.0))) ** years) for item in portfolio)
        best_alternative_saving = fv_optimized - fv_current

        return {
            "annual_fees_total": round(annual_fees_total, 2),
            "ten_year_drag": round(ten_year_drag, 2),
            "worst_fund": worst_fund['fund_name'] if worst_fund else None,
            "best_alternative_saving": round(best_alternative_saving, 2)
        }

    # 5. --- TAX REGIMES COMPARISON ---

    @staticmethod
    def calculate_hra_exemption(basic: float, hra_received: float, rent_paid: float, is_metro: bool) -> float:
        """
        Calculate exact HRA exemption based on Indian tax rules.
        """
        # Condition 1: Actual HRA received
        # Condition 2: Rent paid minus 10% of basic
        # Condition 3: 50% (Metro) or 40% (Non-metro) of basic
        
        c2 = max(0.0, rent_paid - (0.1 * basic))
        c3 = (0.5 * basic) if is_metro else (0.4 * basic)
        
        return float(min(hra_received, c2, c3))

    @staticmethod
    def compare_tax_regimes(
        gross_salary: float,
        basic: float,
        hra_received: float,
        rent_paid: float,
        city_type: str,
        deductions_80c: float,
        deductions_80d: float,
        nps_80ccd: float,
        home_loan_interest: float,
        other_deductions: float
    ) -> Dict[str, Any]:
        """
        Side-by-side comparison of Indian Tax Regimes (FY 2024-25).
        """
        is_metro = city_type.lower() == "metro"
        missed_deductions_list = []

        # --- Old Regime Calculation ---
        hra_exemption = FinancialCalculator.calculate_hra_exemption(basic, hra_received, rent_paid, is_metro)
        
        # Caps
        d80c = min(deductions_80c, 150000.0)
        d80d = min(deductions_80d, 25000.0)  # non-senior
        d_nps = min(nps_80ccd, 50000.0)      # Sec 80CCD(1B) additional
        
        std_deduct_old = 50000.0
        taxable_old = gross_salary - std_deduct_old - hra_exemption - d80c - d80d - d_nps - home_loan_interest - other_deductions
        taxable_old = max(0.0, taxable_old)
        
        # Slabs Old (24-25)
        def calc_old_slabs(income: float) -> float:
            if income <= 250000: return 0.0
            tax = 0.0
            if income > 1000000:
                tax += (income - 1000000) * 0.30
                income = 1000000
            if income > 500000:
                tax += (income - 500000) * 0.20
                income = 500000
            if income > 250000:
                tax += (income - 250000) * 0.05
            return tax

        base_tax_old = calc_old_slabs(taxable_old)
        if taxable_old <= 500000: base_tax_old = 0.0 # Rebate 87A
        final_tax_old = base_tax_old * 1.04 # 4% Cess

        # --- New Regime Calculation (FY 24-25) ---
        std_deduct_new = 75000.0
        taxable_new = max(0.0, gross_salary - std_deduct_new)
        
        # New Slabs (Post-2024 Budget): 3, 7, 10, 12, 15
        def calc_new_slabs(income: float) -> float:
            if income <= 300000: return 0.0
            tax = 0.0
            if income > 1500000:
                tax += (income - 1500000) * 0.30
                income = 1500000
            if income > 1200000:
                tax += (income - 1200000) * 0.20
                income = 1200000
            if income > 1000000:
                tax += (income - 1000000) * 0.15
                income = 1000000
            if income > 700000:
                tax += (income - 700000) * 0.10
                income = 700000
            if income > 300000:
                tax += (income - 300000) * 0.05
            return tax

        base_tax_new = calc_new_slabs(taxable_new)
        if taxable_new <= 700000: base_tax_new = 0.0 # Rebate 87A
        final_tax_new = base_tax_new * 1.04 # 4% Cess

        # Missed Deductions Analysis (Old Regime context)
        if deductions_80c < 150000: missed_deductions_list.append(f"Section 80C: Gap of ₹{150000 - deductions_80c}")
        if deductions_80d < 25000: missed_deductions_list.append(f"Section 80D: Gap of ₹{25000 - deductions_80d}")
        if nps_80ccd < 50000: missed_deductions_list.append(f"Section 80CCD(1B): Gap of ₹{50000 - nps_80ccd} for NPS")

        return {
            "old_tax": round(final_tax_old, 2),
            "new_tax": round(final_tax_new, 2),
            "old_net_salary": round(gross_salary - final_tax_old, 2),
            "new_net_salary": round(gross_salary - final_tax_new, 2),
            "recommended_regime": "NEW" if final_tax_new <= final_tax_old else "OLD",
            "savings_amount": round(abs(final_tax_new - final_tax_old), 2),
            "missed_deductions_list": missed_deductions_list
        }

    # 6. --- COUPLE OPTIMIZATION ---

    @staticmethod
    def calculate_couple_optimization(partner1: Dict[str, Any], partner2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize tax liability for a couple by testing redistribution scenarios.
        """
        def get_total_tax(p1_data, p2_data):
            t1 = FinancialCalculator.compare_tax_regimes(**p1_data)
            t2 = FinancialCalculator.compare_tax_regimes(**p2_data)
            return min(t1['old_tax'], t1['new_tax']) + min(t2['old_tax'], t2['new_tax']), t1, t2

        # Base case
        base_total, t1_base, t2_base = get_total_tax(partner1, partner2)
        best_savings = 0.0
        best_scenario = "Current Status"

        # Higher earner logic
        if partner1['gross_salary'] >= partner2['gross_salary']:
            he, le = partner1.copy(), partner2.copy()
            he_key, le_key = "Partner 1", "Partner 2"
        else:
            he, le = partner2.copy(), partner1.copy()
            he_key, le_key = "Partner 2", "Partner 1"

        # Scenario 2: Shift 80C to higher earner (if lower earner doesn't need it)
        # Often occurs in life insurance or joint home loans
        # (Mocking by assuming shared pool of 1.5L)
        s2_he = he.copy(); s2_le = le.copy()
        s2_he['deductions_80c'] = 150000.0; s2_le['deductions_80c'] = 0.0
        s2_tax, _, _ = get_total_tax(s2_he, s2_le)
        if (base_total - s2_tax) > best_savings:
            best_savings = base_total - s2_tax
            best_scenario = f"Shift 80C to {he_key} (Higher Earner)"

        # Scenario 3: HRA in higher earner name (if possible)
        s3_he = he.copy(); s3_le = le.copy()
        combined_rent = he['rent_paid'] + le['rent_paid']
        s3_he['rent_paid'] = combined_rent; s3_le['rent_paid'] = 0.0
        s3_tax, _, _ = get_total_tax(s3_he, s3_le)
        if (base_total - s3_tax) > best_savings:
            best_savings = base_total - s3_tax
            best_scenario = f"Claim HRA primarily via {he_key}"

        return {
            "combined_base_tax": round(base_total, 2),
            "optimized_combined_tax": round(base_total - best_savings, 2),
            "annual_savings": round(best_savings, 2),
            "best_scenario": best_scenario
        }

    # 7. --- FIRE NUMBER ---

    @staticmethod
    def calculate_fire_number(monthly_expenses: float, inflation: float = 0.06, safe_withdrawal_rate: float = 0.04) -> Dict[str, Any]:
        """
        Calculate corpus needed for Financial Independence / Early Retirement.
        """
        annual_expenses = monthly_expenses * 12
        # Basic 4% rule (Rule of 25)
        # But we adjust for safe_withdrawal_rate directly: corpus = annual_exp / SWR
        fire_corpus = annual_expenses / safe_withdrawal_rate
        
        return {
            "fire_corpus": round(fire_corpus, 2),
            "monthly_passive_income_at_retirement": round(fire_corpus * safe_withdrawal_rate / 12, 2),
            "years_of_runway": round(1 / safe_withdrawal_rate, 1)
        }


# --- TEST SUITE ---
if __name__ == "__main__":
    calc = FinancialCalculator()
    
    print("--- 1. XIRR TEST ---")
    cashflows = [-100000, -50000, 200000]
    dates = [date(2022, 1, 1), date(2023, 1, 1), date(2024, 1, 1)]
    print(f"XIRR: {calc.calculate_xirr(cashflows, dates)*100:.2f}%")

    print("\n--- 2. SIP TEST (12L Goal, 10 Years) ---")
    sip = calc.calculate_sip_for_goal(1200000, 10, 12, 6)
    print(f"Monthly SIP: ₹{sip['monthly_sip']}, Future Goal: ₹{sip['future_goal_value']}")

    print("\n--- 3. OVERLAP TEST ---")
    fund_holdings = {
        "HDFC Top 100": ["Reliance", "HDFCBank", "ICICI", "Infosys"],
        "SBI Bluechip": ["Reliance", "ICICI", "TCS", "Infosys", "L&T"]
    }
    overlap = calc.calculate_portfolio_overlap(fund_holdings)
    print(f"Overlap {overlap['highest_overlap_pair']}: {overlap['highest_overlap']}%")

    print("\n--- 4. TAX COMPARE (12L Salary) ---")
    tax = calc.compare_tax_regimes(
        gross_salary=1200000, basic=500000, hra_received=200000, 
        rent_paid=180000, city_type="metro", deductions_80c=100000, 
        deductions_80d=15000, nps_80ccd=0, home_loan_interest=0, other_deductions=0
    )
    print(f"Old Tax: ₹{tax['old_tax']}, New Tax: ₹{tax['new_tax']}, Recommended: {tax['recommended_regime']}")

    print("\n--- 5. FIRE TEST ---")
    fire = calc.calculate_fire_number(monthly_expenses=50000)
    print(f"FIRE Corpus: ₹{fire['fire_corpus']:,.2f}")
