"""
FinSaarthi — Development Mock API Server
==========================================
Lightweight FastAPI server that returns mock data so the frontend
can be demonstrated without requiring LangChain/Gemini dependencies.

Usage: python dev_server.py
"""

import os
import json
import random
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Pydantic Models (same as api.py) ---

class PortfolioAnalysisResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class FIREGoal(BaseModel):
    name: str
    amount: float
    years: int

class FIREPlanRequest(BaseModel):
    current_age: int
    target_retirement_age: int
    monthly_income: float
    monthly_expenses: float
    existing_corpus: float
    inflation_rate: float = 6.0
    expected_return: float = 12.0
    goals: List[FIREGoal] = []

class FIREPlanResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class TaxAnalysisResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class PartnerProfile(BaseModel):
    name: str
    salary: float

class CoupleOptimizationRequest(BaseModel):
    partner1: PartnerProfile
    partner2: PartnerProfile
    shared_goals: List[Dict[str, Any]] = []

class CoupleOptimizationResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    modules_loaded: List[str]
    knowledge_base_ready: bool
    timestamp: str

# --- In-memory audit log ---
audit_log = []

def add_audit(agent: str, action: str, output: str):
    audit_log.append({
        "timestamp": datetime.now().isoformat(),
        "agent_name": agent,
        "action": action,
        "input_summary": "",
        "output_summary": output,
        "tools_called": ["pdf_parser", "financial_calc"] if "portfolio" in agent else ["financial_calc"],
        "duration_ms": random.randint(200, 1500),
    })

# --- FastAPI App ---

app = FastAPI(title="FinSaarthi Dev API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        modules_loaded=["portfolio", "fire", "tax", "couple"],
        knowledge_base_ready=True,
        timestamp=datetime.now().isoformat(),
    )

@app.post("/api/portfolio/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(
    cams_pdf: UploadFile = File(...),
    risk_profile: str = Form("moderate"),
):
    add_audit("portfolio_agent", "analyze_portfolio", f"Analyzed {cams_pdf.filename} with {risk_profile} risk")

    holdings = [
        {"name": "HDFC Mid-Cap Opportunites", "value": 285000, "invested": 220000, "xirr": 18.4},
        {"name": "Parag Parikh Flexi Cap", "value": 410000, "invested": 350000, "xirr": 14.2},
        {"name": "SBI Small Cap Fund", "value": 192000, "invested": 150000, "xirr": 22.1},
        {"name": "ICICI Pru Balanced Advantage", "value": 320000, "invested": 300000, "xirr": 9.8},
        {"name": "Axis Nifty 50 Index", "value": 175000, "invested": 160000, "xirr": 11.5},
        {"name": "Nippon India Liquid Fund", "value": 100000, "invested": 98000, "xirr": 6.2},
    ]

    total_current = sum(h["value"] for h in holdings)
    total_invested = sum(h["invested"] for h in holdings)
    avg_xirr = sum(h["xirr"] for h in holdings) / len(holdings)

    return PortfolioAnalysisResponse(
        success=True,
        data={
            "holdings": holdings,
            "total_current_value": total_current,
            "total_invested": total_invested,
            "avg_xirr": avg_xirr,
            "risk_profile": risk_profile,
            "rebalancing_plan": (
                f"Based on your {risk_profile} risk profile, your portfolio is well-diversified across "
                f"6 funds with a total value of ₹{total_current:,.0f}. "
                f"Consider reducing overlap between HDFC Mid-Cap and SBI Small Cap (32% stock overlap). "
                f"Your overall XIRR of {avg_xirr:.1f}% outperforms the Nifty 50 benchmark of 12.3%."
            ),
            "asset_allocation": {
                "Large Cap": 33.4,
                "Mid Cap": 19.2,
                "Small Cap": 12.9,
                "Flexi Cap": 27.6,
                "Debt/Liquid": 6.9,
            },
        },
    )

@app.post("/api/fire/plan", response_model=FIREPlanResponse)
async def plan_fire(request: FIREPlanRequest):
    years = request.target_retirement_age - request.current_age
    fire_corpus = request.monthly_expenses * 12 * 25
    real_return = (request.expected_return - request.inflation_rate) / 100
    
    # Simple SIP calculation
    monthly_rate = request.expected_return / 100 / 12
    n_months = years * 12
    future_corpus_needed = fire_corpus * ((1 + request.inflation_rate / 100) ** years)
    
    if monthly_rate > 0 and n_months > 0:
        existing_fv = request.existing_corpus * ((1 + monthly_rate) ** n_months)
        gap = max(0, future_corpus_needed - existing_fv)
        monthly_sip = gap * monthly_rate / (((1 + monthly_rate) ** n_months) - 1) if gap > 0 else 0
    else:
        monthly_sip = 0
        existing_fv = request.existing_corpus

    add_audit("fire_agent", "calculate_plan", f"FIRE Corpus: ₹{fire_corpus:,.0f}")

    # Year-wise projection
    projection = []
    corpus = request.existing_corpus
    for y in range(years + 1):
        projection.append({"year": y, "age": request.current_age + y, "corpus": round(corpus)})
        for m in range(12):
            corpus = corpus * (1 + monthly_rate) + monthly_sip

    return FIREPlanResponse(
        success=True,
        data={
            "fire_metrics": {
                "fire_corpus": round(fire_corpus),
                "inflation_adjusted_corpus": round(future_corpus_needed),
                "monthly_sip_needed": round(monthly_sip),
            },
            "sip_calc": {
                "monthly_sip_required": round(monthly_sip),
                "existing_fv": round(existing_fv),
                "gap": round(max(0, future_corpus_needed - existing_fv)),
            },
            "fire_number": round(fire_corpus),
            "monthly_sip_required": round(monthly_sip),
            "year_wise_projection": projection,
            "user_request": request.dict(),
        },
    )

@app.post("/api/tax/analyze", response_model=TaxAnalysisResponse)
async def analyze_tax(
    form16_pdf: Optional[UploadFile] = File(None),
    manual_data: Optional[str] = Form(None),
):
    if manual_data:
        data = json.loads(manual_data)
    elif form16_pdf:
        data = {
            "gross_salary": 1500000,
            "basic": 600000,
            "hra_received": 180000,
            "rent_paid": 300000,
            "city_type": "metro",
            "deductions_80c": 150000,
            "deductions_80d": 25000,
            "nps_80ccd": 50000,
            "home_loan_interest": 0,
            "other_deductions": 0,
        }
    else:
        data = {"gross_salary": 1000000}

    gross = data.get("gross_salary", 1000000)
    ded_80c = data.get("deductions_80c", 0)
    ded_80d = data.get("deductions_80d", 0)
    nps = data.get("nps_80ccd", 0)
    hra = min(data.get("hra_received", 0), data.get("rent_paid", 0) * 0.4 if data.get("city_type") == "metro" else data.get("rent_paid", 0) * 0.3)
    home_loan = data.get("home_loan_interest", 0)

    # Old regime calculation (simplified)
    old_taxable = gross - 50000 - min(ded_80c, 150000) - min(ded_80d, 75000) - min(nps, 50000) - hra - min(home_loan, 200000)
    old_taxable = max(0, old_taxable)
    old_tax = _calc_old_tax(old_taxable)

    # New regime calculation (simplified)
    new_taxable = max(0, gross - 75000)
    new_tax = _calc_new_tax(new_taxable)

    recommended = "old" if old_tax < new_tax else "new"
    saving = abs(old_tax - new_tax)

    add_audit("tax_agent", "tax_optimization", f"Recommended: {recommended} regime, savings: ₹{saving:,.0f}")

    return TaxAnalysisResponse(
        success=True,
        data={
            "old_regime_tax": round(old_tax),
            "new_regime_tax": round(new_tax),
            "recommended_regime": recommended,
            "tax_saving_potential": round(saving),
            "gross_salary": gross,
            "deductions_used": {
                "80C": min(ded_80c, 150000),
                "80D": min(ded_80d, 75000),
                "NPS 80CCD": min(nps, 50000),
                "HRA": round(hra),
                "Home Loan": min(home_loan, 200000),
            },
        },
    )

def _calc_old_tax(taxable):
    if taxable <= 250000: return 0
    elif taxable <= 500000: return (taxable - 250000) * 0.05
    elif taxable <= 1000000: return 12500 + (taxable - 500000) * 0.2
    else: return 112500 + (taxable - 1000000) * 0.3

def _calc_new_tax(taxable):
    slabs = [(300000, 0), (700000, 0.05), (1000000, 0.1), (1200000, 0.15), (1500000, 0.2), (float('inf'), 0.3)]
    tax = 0
    prev = 0
    for limit, rate in slabs:
        if taxable <= prev: break
        bracket = min(taxable, limit) - prev
        tax += bracket * rate
        prev = limit
    return tax

@app.post("/api/couple/optimize", response_model=CoupleOptimizationResponse)
async def optimize_couple(request: CoupleOptimizationRequest):
    s1 = request.partner1.salary
    s2 = request.partner2.salary

    # Calculate individual taxes (new regime for simplicity)
    t1_old = _calc_old_tax(max(0, s1 - 250000))
    t2_old = _calc_old_tax(max(0, s2 - 250000))
    
    # Optimized: assign 80C/HRA to higher earner
    t1_opt = _calc_old_tax(max(0, s1 - 50000 - 150000 - 50000))
    t2_opt = _calc_old_tax(max(0, s2 - 50000 - 100000))
    
    separate_total = t1_old + t2_old
    joint_total = t1_opt + t2_opt
    savings = max(0, separate_total - joint_total)

    add_audit("couple_agent", "optimize_tax", f"Joint savings: ₹{savings:,.0f}")

    return CoupleOptimizationResponse(
        success=True,
        data={
            "annual_savings": round(savings),
            "partner1_tax": round(t1_opt),
            "partner2_tax": round(t2_opt),
            "separate_tax_total": round(separate_total),
            "joint_tax_total": round(joint_total),
            "strategy_summary": (
                f"By assigning ₹1.5L of 80C investments and ₹50K NPS to {request.partner1.name} "
                f"(higher earner at ₹{s1:,.0f}), and ₹1L of 80C to {request.partner2.name}, "
                f"you save ₹{savings:,.0f} annually compared to filing independently."
            ),
        },
    )

@app.get("/api/audit/recent")
async def get_audit_logs():
    return audit_log[-50:]

if __name__ == "__main__":
    import uvicorn
    print("🚀 FinSaarthi Dev Server starting on http://localhost:8000")
    print("   Frontend should connect from http://localhost:5173")
    uvicorn.run(app, host="0.0.0.0", port=8000)
