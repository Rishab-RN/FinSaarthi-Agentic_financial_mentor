"""
FinSaarthi — Shared LangGraph State Definition
================================================
Central TypedDict that flows through every agent node in the LangGraph pipeline.
Each module (Portfolio X-Ray, FIRE Planner, Tax Wizard, Couple Planner) reads
and writes to its own namespace within this shared state, enabling clean
multi-agent coordination without state collisions.

File: state.py (project root)
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, TypedDict


class UserProfile(TypedDict, total=False):
    """Demographic and financial profile collected during onboarding."""

    name: str
    age: int
    email: str
    phone: str
    annual_income: float
    monthly_expenses: float
    existing_investments: float
    risk_tolerance: str  # "conservative" | "moderate" | "aggressive"
    tax_regime: str  # "old" | "new"
    pan_number: str
    city: str


class PortfolioData(TypedDict, total=False):
    """State namespace for MF Portfolio X-Ray module."""

    raw_pdf_text: str
    parsed_transactions: List[Dict[str, Any]]
    fund_holdings: List[Dict[str, Any]]
    xirr_results: Dict[str, float]  # fund_name → XIRR %
    overlap_matrix: Dict[str, Dict[str, float]]  # fund_pair → overlap %
    rebalancing_suggestions: List[Dict[str, Any]]
    total_current_value: float
    total_invested: float
    asset_allocation: Dict[str, float]  # category → %


class FIREData(TypedDict, total=False):
    """State namespace for FIRE Path Planner module."""

    target_retirement_age: int
    current_age: int
    monthly_income: float
    monthly_expenses: float
    existing_corpus: float
    expected_return_rate: float  # annual %
    inflation_rate: float  # annual %
    fire_number: float
    monthly_sip_required: float
    year_wise_projection: List[Dict[str, Any]]
    goal_breakdown: List[Dict[str, Any]]
    sip_roadmap: List[Dict[str, Any]]


class TaxData(TypedDict, total=False):
    """State namespace for Tax Wizard module."""

    raw_form16_text: str
    parsed_income: Dict[str, float]
    declared_deductions: Dict[str, float]
    missed_deductions: List[Dict[str, Any]]
    old_regime_tax: float
    new_regime_tax: float
    recommended_regime: str
    tax_saving_potential: float
    section_wise_analysis: Dict[str, Any]


class CoupleData(TypedDict, total=False):
    """State namespace for Couple's Money Planner module."""

    partner_a_profile: Dict[str, Any]
    partner_b_profile: Dict[str, Any]
    combined_income: float
    combined_expenses: float
    joint_goals: List[Dict[str, Any]]
    individual_tax_a: Dict[str, float]
    individual_tax_b: Dict[str, float]
    optimized_tax_split: Dict[str, Any]
    joint_sip_plan: List[Dict[str, Any]]
    joint_fire_number: float
    savings_vs_separate: float  # ₹ saved by joint optimization


class AuditEntry(TypedDict):
    """Single audit log entry written by every agent action."""

    timestamp: str
    agent_name: str
    action: str
    input_summary: str
    output_summary: str
    tools_called: List[str]
    duration_ms: int


class FinSaarthiState(TypedDict, total=False):
    """
    Master LangGraph state shared across all agent nodes.

    Convention:
        - Each module writes ONLY to its own *_data namespace.
        - orchestrator.py reads module_selected to route to the correct agent.
        - audit_log is append-only; every agent adds its own AuditEntry.
        - final_response is set by the last agent before returning to the user.
        - error_message is set on any unrecoverable failure.

    Usage in LangGraph:
        from state import FinSaarthiState
        workflow = StateGraph(FinSaarthiState)
    """

    # ── User Context ──────────────────────────────────────────────────────
    user_profile: UserProfile
    uploaded_file_path: Optional[str]
    module_selected: str  # "portfolio" | "fire" | "tax" | "couple"

    # ── Orchestrator Routing ──────────────────────────────────────────────
    intent: str  # resolved intent after classification
    needs_more_input: bool  # True if required fields are missing
    missing_fields: List[str]  # list of field names the UI must collect

    # ── Module-Specific Data ──────────────────────────────────────────────
    portfolio_data: PortfolioData
    fire_data: FIREData
    tax_data: TaxData
    couple_data: CoupleData

    # ── Agent Outputs ─────────────────────────────────────────────────────
    agent_results: Dict[str, Any]  # intermediate results from current agent
    final_response: str  # formatted markdown response for the user

    # ── Observability ─────────────────────────────────────────────────────
    audit_log: List[AuditEntry]
    error_message: str

    # ── Session Metadata ──────────────────────────────────────────────────
    session_id: str
    created_at: str
    last_updated_at: str


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================

def create_initial_state(
    module: str,
    session_id: Optional[str] = None,
) -> FinSaarthiState:
    """
    Create a clean initial state for a given module.

    Parameters:
        module (str): One of "portfolio", "fire", "tax", "couple".
        session_id (str, optional): Unique session ID. Generated if not provided.

    Returns:
        FinSaarthiState: A fresh state dict ready for the LangGraph pipeline.
    """
    import uuid

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return FinSaarthiState(
        user_profile={},
        uploaded_file_path=None,
        module_selected=module,
        intent="",
        needs_more_input=False,
        missing_fields=[],
        portfolio_data={},
        fire_data={},
        tax_data={},
        couple_data={},
        agent_results={},
        final_response="",
        audit_log=[],
        error_message="",
        session_id=session_id or str(uuid.uuid4()),
        created_at=now,
        last_updated_at=now,
    )


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate_state_for_module(state: FinSaarthiState) -> tuple:
    """
    Check all required fields are present for the selected module.

    Parameters:
        state (FinSaarthiState): Current state.

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_missing_fields)
    """
    module = state.get("module_selected", "")
    missing: List[str] = []
    profile = state.get("user_profile", {})

    if module == "portfolio":
        if not state.get("uploaded_file_path"):
            missing.append("uploaded_file_path")
        if not profile.get("risk_tolerance"):
            missing.append("user_profile.risk_tolerance")

    elif module == "fire":
        fd = state.get("fire_data", {})
        for field in ("current_age", "monthly_income", "monthly_expenses"):
            if not fd.get(field) and not profile.get("age" if field == "current_age" else field.replace("monthly_", "")):
                missing.append(f"fire_data.{field}")
        goals = fd.get("goal_breakdown", [])
        if not goals:
            missing.append("fire_data.goals (empty)")

    elif module == "tax":
        has_pdf = bool(state.get("uploaded_file_path"))
        td = state.get("tax_data", {})
        has_manual = bool(td.get("parsed_income", {}).get("gross_salary") or profile.get("annual_income"))
        if not has_pdf and not has_manual:
            missing.append("uploaded_file_path OR tax_data.gross_salary")

    elif module == "couple":
        cd = state.get("couple_data", {})
        if not cd.get("partner_a_profile", {}).get("gross_salary"):
            missing.append("couple_data.partner_a_profile.gross_salary")
        if not cd.get("partner_b_profile", {}).get("gross_salary"):
            missing.append("couple_data.partner_b_profile.gross_salary")
        if not cd.get("joint_goals"):
            missing.append("couple_data.joint_goals")

    return (len(missing) == 0, missing)


# ==============================================================================
# AUDIT HELPER
# ==============================================================================

def add_audit_entry(
    state: FinSaarthiState,
    agent: str,
    action: str,
    summary: str,
) -> FinSaarthiState:
    """
    Append a timestamped audit entry to state and return updated state.

    Parameters:
        state: Current state.
        agent (str): Agent name.
        action (str): Action performed.
        summary (str): Human-readable summary.

    Returns:
        FinSaarthiState: State with new audit entry appended.
    """
    entry: AuditEntry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent_name": agent,
        "action": action,
        "input_summary": "",
        "output_summary": summary,
        "tools_called": [],
        "duration_ms": 0,
    }

    audit_log = list(state.get("audit_log", []))
    audit_log.append(entry)

    return {**state, "audit_log": audit_log, "last_updated_at": entry["timestamp"]}

