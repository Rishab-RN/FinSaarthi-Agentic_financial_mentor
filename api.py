import os
import shutil
import tempfile
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Local imports
from state import FinSaarthiState, UserProfile
from tools.audit_logger import AuditLogger
from tools.financial_calc import FinancialCalculator
from tools.pdf_parser import PDFParser

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finsaarthi_api")

# --- Pydantic Models for Requests/Responses ---

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

# --- FastAPI App Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global resources if needed
    app.state.audit_logger = AuditLogger()
    logger.info("FinSaarthi API Started")
    yield
    logger.info("FinSaarthi API Shutdown")

app = FastAPI(title="FinSaarthi API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routes ---

@app.post("/api/portfolio/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(
    background_tasks: BackgroundTasks,
    cams_pdf: UploadFile = File(...),
    risk_profile: str = Form("moderate")
):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, cams_pdf.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(cams_pdf.file, f)
        
        # 1. Parse PDF
        results = PDFParser.parse_cams_cas(file_path)
        
        # 2. Add risk profile context
        results["risk_profile"] = risk_profile
        
        return PortfolioAnalysisResponse(success=True, data=results)
    finally:
        background_tasks.add_task(shutil.rmtree, temp_dir)

@app.post("/api/fire/plan", response_model=FIREPlanResponse)
async def plan_fire(request: FIREPlanRequest):
    results = FinancialCalculator.calculate_fire_plan(
        current_age=request.current_age,
        target_retirement_age=request.target_retirement_age,
        monthly_expenses=request.monthly_expenses,
        existing_corpus=request.existing_corpus,
        inflation_rate=6.0, # Using defaults for now
        expected_return_rate=12.0
    )
    return FIREPlanResponse(success=True, data=results)

@app.post("/api/tax/analyze", response_model=TaxAnalysisResponse)
async def analyze_tax(
    background_tasks: BackgroundTasks,
    form16_pdf: Optional[UploadFile] = File(None),
    manual_data: Optional[str] = Form(None)
):
    results = {}
    if form16_pdf:
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, form16_pdf.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(form16_pdf.file, f)
        
        parsed_data = PDFParser.parse_form16(file_path)
        results = FinancialCalculator.calculate_indian_tax(
            gross_salary=parsed_data["gross_salary"],
            deductions_80c=parsed_data["sec_80c"],
            deductions_80d=parsed_data["sec_80d"],
            hra_exemption=parsed_data["hra"]
        )
        background_tasks.add_task(shutil.rmtree, temp_dir)
    elif manual_data:
        data = json.loads(manual_data)
        results = FinancialCalculator.calculate_indian_tax(
            gross_salary=data.get("gross_salary", 0),
            deductions_80c=data.get("section_80c", 0),
            deductions_80d=data.get("section_80d", 0),
            hra_exemption=data.get("hra_received", 0)
        )
    else:
        raise HTTPException(status_code=400, detail="Missing data")
    return TaxAnalysisResponse(success=True, data=results)

@app.post("/api/couple/optimize", response_model=CoupleOptimizationResponse)
async def optimize_couple(request: CoupleOptimizationRequest):
    # Joint optimization uses the calculator for both
    p1_tax = FinancialCalculator.calculate_indian_tax(request.partner1.salary)
    p2_tax = FinancialCalculator.calculate_indian_tax(request.partner2.salary)
    
    # Combined analysis logic here
    results = {
        "p1_results": p1_tax,
        "p2_results": p2_tax,
        "total_tax": p1_tax["new_regime"]["tax_payable"] + p2_tax["new_regime"]["tax_payable"],
        "combined_income": request.partner1.salary + request.partner2.salary
    }
    return CoupleOptimizationResponse(success=True, data=results)

@app.get("/api/portfolio/report")
async def get_report():
    # Simplest possible file response for testing
    content = b"Mock PDF Content"
    fd, path = tempfile.mkstemp(suffix=".pdf")
    with open(path, "wb") as f: f.write(content)
    return FileResponse(path, filename="report.pdf")

@app.get("/api/audit/recent")
async def get_audit():
    return [{"timestamp": datetime.now().isoformat(), "action": "mock_action", "status": "success"}]

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        modules_loaded=["portfolio", "fire", "tax", "couple"],
        knowledge_base_ready=True,
        timestamp=datetime.now().isoformat()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
