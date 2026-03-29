"""
FinSaarthi — Agent Integration Test
=====================================
Tests all 4 agents with realistic dummy data. No pytest needed.
Run: python test_agents.py

File: test_agents.py (project root)
"""

import sys
import os
import traceback
from datetime import date

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Test results tracker ──────────────────────────────────────────────────────
RESULTS = {"passed": 0, "failed": 0, "errors": []}


def test_pass(name: str, detail: str = ""):
    RESULTS["passed"] += 1
    print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))


def test_fail(name: str, detail: str = ""):
    RESULTS["failed"] += 1
    RESULTS["errors"].append(f"{name}: {detail}")
    print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


# ==============================================================================
# TEST 1: State Module
# ==============================================================================

def test_state():
    print("\n" + "=" * 60)
    print("TEST 1: state.py")
    print("=" * 60)
    try:
        from state import (
            FinSaarthiState, create_initial_state,
            validate_state_for_module, add_audit_entry,
        )

        # create_initial_state
        state = create_initial_state("tax", session_id="test-001")
        assert state["module_selected"] == "tax", "module_selected wrong"
        assert state["session_id"] == "test-001", "session_id wrong"
        assert state["needs_more_input"] == False, "needs_more_input wrong"
        test_pass("create_initial_state", f"session={state['session_id']}")

        # validate — should fail (no tax data)
        is_valid, missing = validate_state_for_module(state)
        assert not is_valid, "Should be invalid with no data"
        assert len(missing) > 0, "Should have missing fields"
        test_pass("validate_state_for_module (missing)", f"missing={missing}")

        # validate — should pass with data
        state["user_profile"] = {"annual_income": 1200000}
        is_valid2, missing2 = validate_state_for_module(state)
        assert is_valid2, f"Should be valid, but missing: {missing2}"
        test_pass("validate_state_for_module (valid)")

        # add_audit_entry
        updated = add_audit_entry(state, "test", "test_action", "test summary")
        assert len(updated["audit_log"]) == 1, "Should have 1 audit entry"
        assert updated["audit_log"][0]["agent_name"] == "test"
        test_pass("add_audit_entry", f"entries={len(updated['audit_log'])}")

    except Exception as e:
        test_fail("state.py", str(e))
        traceback.print_exc()


# ==============================================================================
# TEST 2: Portfolio Agent
# ==============================================================================

def test_portfolio_agent():
    print("\n" + "=" * 60)
    print("TEST 2: PortfolioAgent")
    print("=" * 60)
    try:
        from agents.portfolio_agent import PortfolioAgent

        # Use a mock LLM that just returns a string
        class MockLLM:
            def invoke(self, prompt):
                class R:
                    content = "Mock rebalancing: Exit high-overlap funds. Increase index allocation. Start SIP this month."
                return R()

        agent = PortfolioAgent(llm=MockLLM(), knowledge_base=None, audit_logger=None)
        test_pass("PortfolioAgent init")

        # Run with fallback demo data (no actual PDF needed)
        result = agent.analyze("dummy_cams.pdf", risk_profile="moderate")

        assert "xirr_by_fund" in result, "Missing xirr_by_fund"
        assert len(result["xirr_by_fund"]) > 0, "xirr_by_fund is empty"
        test_pass("xirr_by_fund", f"{len(result['xirr_by_fund'])} funds analyzed")

        for fund, data in result["xirr_by_fund"].items():
            assert "xirr_pct" in data, f"Missing xirr_pct for {fund}"
            print(f"    📊 {fund}: XIRR={data['xirr_pct']:.1f}%, Invested=₹{data['invested_amount']:,.0f}, Current=₹{data['current_value']:,.0f}")

        assert "portfolio_xirr" in result, "Missing portfolio_xirr"
        pxirr = result["portfolio_xirr"]
        assert -0.5 < pxirr < 1.0, f"Portfolio XIRR out of range: {pxirr}"
        test_pass("portfolio_xirr", f"{pxirr * 100:.2f}%")

        assert "overlap_analysis" in result, "Missing overlap_analysis"
        overlap = result["overlap_analysis"]
        assert "overlap_matrix" in overlap, "Missing overlap_matrix"
        test_pass("overlap_analysis", f"highest={overlap.get('highest_overlap_pct', 0) * 100:.1f}%")

        assert "expense_analysis" in result, "Missing expense_analysis"
        test_pass("expense_analysis", f"annual_fees=₹{result['expense_analysis'].get('annual_fees_total', 0):,.0f}")

        assert "benchmark_comparison" in result, "Missing benchmark_comparison"
        test_pass("benchmark_comparison", result["benchmark_comparison"].get("overall_verdict", "")[:60])

        assert "rebalancing_plan" in result, "Missing rebalancing_plan"
        assert len(result["rebalancing_plan"]) > 20, "Rebalancing plan too short"
        test_pass("rebalancing_plan", f"{len(result['rebalancing_plan'].split())} words")

        assert "charts_data" in result, "Missing charts_data"
        test_pass("charts_data present")

    except Exception as e:
        test_fail("PortfolioAgent", str(e))
        traceback.print_exc()


# ==============================================================================
# TEST 3: FIRE Agent
# ==============================================================================

def test_fire_agent():
    print("\n" + "=" * 60)
    print("TEST 3: FIREAgent")
    print("=" * 60)
    try:
        from agents.fire_agent import FIREAgent

        class MockLLM:
            def invoke(self, prompt):
                class R:
                    content = "Mock FIRE plan: Start SIPs of ₹30,000/month. Buy term insurance. Build emergency fund."
                return R()

        agent = FIREAgent(llm=MockLLM(), knowledge_base=None, audit_logger=None)
        test_pass("FIREAgent init")

        fire_data = {
            "age": 28, "monthly_income": 150000, "monthly_expenses": 70000,
            "existing_investments": {"mf": 500000, "pf": 200000, "fd": 100000},
            "goals": [
                {"name": "Dream Home", "amount_today": 7500000, "years": 8},
                {"name": "Child Education", "amount_today": 2000000, "years": 15},
            ],
            "target_retirement_age": 50, "risk_profile": "moderate",
        }

        result = agent.plan(fire_data)

        # FIRE number
        assert "fire_number" in result, "Missing fire_number"
        fire_corpus = result["fire_number"]["fire_corpus"]
        assert fire_corpus > 10000000, f"FIRE corpus too low: {fire_corpus}"
        test_pass("fire_number", f"₹{fire_corpus:,.0f} (₹{fire_corpus / 10000000:.1f} Cr)")

        # Goals
        assert "goals_breakdown" in result, "Missing goals_breakdown"
        goals = result["goals_breakdown"]
        assert len(goals) >= 3, f"Expected ≥3 goals (2 + retirement), got {len(goals)}"
        test_pass("goals_breakdown", f"{len(goals)} goals decomposed")
        for g in goals:
            print(f"    🎯 {g['goal_name']}: SIP ₹{g['monthly_sip_needed']:,.0f}/mo for {g['years']}yrs → ₹{g['future_value']:,.0f}")

        # SIP feasibility
        assert "sip_feasibility" in result, "Missing sip_feasibility"
        sip = result["sip_feasibility"]
        assert sip["total_sip_needed"] > 0, "Total SIP should be > 0"
        test_pass("sip_feasibility", f"Total SIP: ₹{sip['total_sip_needed']:,.0f}/mo, Feasible: {sip['is_feasible']}")

        # Insurance
        assert "insurance_check" in result, "Missing insurance_check"
        test_pass("insurance_check", f"Alerts: {len(result['insurance_check'].get('alerts', []))}")

        # Roadmap
        assert "monthly_roadmap" in result, "Missing monthly_roadmap"
        assert len(result["monthly_roadmap"]) >= 4, "Roadmap too short"
        test_pass("monthly_roadmap", f"{len(result['monthly_roadmap'])} milestones")

        # Projection
        assert "year_wise_projection" in result, "Missing year_wise_projection"
        proj = result["year_wise_projection"]
        years_to_retire = 50 - 28
        assert len(proj) == years_to_retire, f"Expected {years_to_retire} years, got {len(proj)}"
        test_pass("year_wise_projection", f"{len(proj)} years, final corpus: ₹{proj[-1]['corpus']:,.0f}")

        # Narrative
        assert "narrative" in result, "Missing narrative"
        test_pass("narrative", f"{len(result['narrative'].split())} words")

    except Exception as e:
        test_fail("FIREAgent", str(e))
        traceback.print_exc()


# ==============================================================================
# TEST 4: Tax Agent
# ==============================================================================

def test_tax_agent():
    print("\n" + "=" * 60)
    print("TEST 4: TaxAgent")
    print("=" * 60)
    try:
        from agents.tax_agent import TaxAgent

        class MockLLM:
            def invoke(self, prompt):
                class R:
                    content = "Mock tax plan: Invest ₹70K in ELSS. Open NPS for ₹50K. Buy health insurance."
                return R()

        agent = TaxAgent(llm=MockLLM(), knowledge_base=None, audit_logger=None)
        test_pass("TaxAgent init")

        manual_inputs = {
            "gross_salary": 1800000, "basic": 720000, "hra_received": 216000,
            "rent_paid": 300000, "city_type": "metro", "deductions_80c_used": 100000,
            "deductions_80d_used": 12000, "nps_used": 0, "home_loan_interest": 0,
            "other_deductions": 0,
        }

        result = agent.analyze(manual_inputs=manual_inputs)

        # Regime comparison
        assert "regime_comparison" in result, "Missing regime_comparison"
        regime = result["regime_comparison"]
        assert regime["old_tax"] > 0, "Old tax should be > 0"
        assert regime["new_tax"] > 0, "New tax should be > 0"
        test_pass("regime_comparison",
                  f"Old: ₹{regime['old_tax']:,.0f}, New: ₹{regime['new_tax']:,.0f} → {regime['recommended_regime']}")

        # Missed deductions
        assert "missed_deductions" in result, "Missing missed_deductions"
        missed = result["missed_deductions"]
        assert len(missed) >= 2, f"Should find ≥2 missed deductions, found {len(missed)}"
        test_pass("missed_deductions", f"Found {len(missed)} gaps")
        for d in missed:
            print(f"    💰 {d['deduction_name']}: gap ₹{d['gap_amount']:,.0f} → saves ₹{d['tax_saving_possible']:,.0f}")

        # Net impact
        assert "net_impact" in result, "Missing net_impact"
        saving = result["net_impact"]["total_tax_saving"]
        test_pass("net_impact", f"Total saving: ₹{saving:,.0f}/year (₹{saving / 12:,.0f}/month)")

        # Investment recommendations
        assert "investment_recommendations" in result, "Missing investment_recommendations"
        invs = result["investment_recommendations"]
        assert len(invs) >= 2, "Should have ≥2 investment recommendations"
        test_pass("investment_recommendations", f"{len(invs)} options ranked")

        # Action plan
        assert "action_plan" in result, "Missing action_plan"
        test_pass("action_plan", f"{len(result['action_plan'].split())} words")

    except Exception as e:
        test_fail("TaxAgent", str(e))
        traceback.print_exc()


# ==============================================================================
# TEST 5: Couple Agent
# ==============================================================================

def test_couple_agent():
    print("\n" + "=" * 60)
    print("TEST 5: CoupleAgent")
    print("=" * 60)
    try:
        from agents.couple_agent import CoupleAgent

        class MockLLM:
            def invoke(self, prompt):
                class R:
                    content = "Mock couple plan: Priya and Rahul should shift HRA, max out NPS, and split SIPs."
                return R()

        agent = CoupleAgent(llm=MockLLM(), knowledge_base=None, audit_logger=None)
        test_pass("CoupleAgent init")

        p1 = {"name": "Priya", "age": 30, "gross_salary": 1800000, "basic": 720000,
              "hra_received": 216000, "rent_paid": 360000, "city": "metro",
              "deductions_80c": 100000, "deductions_80d": 0, "nps_existing": 0,
              "existing_investments": {"mf": 500000, "pf": 300000}, "monthly_expenses": 50000}

        p2 = {"name": "Rahul", "age": 32, "gross_salary": 1200000, "basic": 480000,
              "hra_received": 144000, "rent_paid": 0, "city": "metro",
              "deductions_80c": 50000, "deductions_80d": 25000, "nps_existing": 0,
              "existing_investments": {"mf": 300000, "pf": 400000}, "monthly_expenses": 40000}

        goals = [{"name": "Dream Home", "amount": 10000000, "years": 6},
                 {"name": "Europe Trip", "amount": 500000, "years": 2}]

        result = agent.optimize(p1, p2, goals)

        # HRA
        assert "hra_optimization" in result, "Missing hra_optimization"
        hra = result["hra_optimization"]
        test_pass("hra_optimization", f"Best: {hra['best_scenario']}, saves ₹{hra['combined_tax_saving']:,.0f}")

        # 80C
        assert "section_80c_optimization" in result, "Missing section_80c_optimization"
        c80 = result["section_80c_optimization"]
        test_pass("80c_optimization", f"Gap: ₹{c80.get('p1_gap', 0) + c80.get('p2_gap', 0):,.0f}")

        # NPS
        assert "nps_optimization" in result, "Missing nps_optimization"
        nps = result["nps_optimization"]
        test_pass("nps_optimization", f"Combined saving: ₹{nps['combined_tax_saving']:,.0f}")

        # Net worth
        assert "net_worth" in result, "Missing net_worth"
        nw = result["net_worth"]
        test_pass("net_worth", f"₹{nw['net_worth']:,.0f} ({nw['net_worth_pct_of_target']:.1f}% of FIRE)")

        # SIP
        assert "sip_allocation" in result, "Missing sip_allocation"
        sip = result["sip_allocation"]
        test_pass("sip_allocation", f"Priya: ₹{sip['p1_total_sip']:,.0f}/mo, Rahul: ₹{sip['p2_total_sip']:,.0f}/mo")

        # Total optimization
        assert "total_optimization" in result, "Missing total_optimization"
        total = result["total_optimization"]
        test_pass("total_optimization",
                  f"Score: {total['optimization_score']}/100, Annual: ₹{total['total_annual_tax_saving']:,.0f}, 10yr: ₹{total['ten_year_invested_value']:,.0f}")

        # Narrative
        assert "narrative" in result, "Missing narrative"
        test_pass("narrative", f"{len(result['narrative'].split())} words")

    except Exception as e:
        test_fail("CoupleAgent", str(e))
        traceback.print_exc()


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    print("🚀 FINSAARTHI AGENT INTEGRATION TEST SUITE 🚀")
    print("=" * 60)

    test_state()
    test_portfolio_agent()
    test_fire_agent()
    test_tax_agent()
    test_couple_agent()

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {RESULTS['passed']} passed, {RESULTS['failed']} failed")
    print("=" * 60)

    if RESULTS["errors"]:
        print("\n❌ FAILURES:")
        for err in RESULTS["errors"]:
            print(f"  - {err}")
    else:
        print("\n🎉 ALL TESTS PASSED! Agents ready for integration.")

    print(f"\n💡 Next step: wire up app.py (Streamlit) and api.py (FastAPI)")
    sys.exit(1 if RESULTS["failed"] > 0 else 0)
