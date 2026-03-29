"""
FinSaarthi — LangGraph Orchestrator
=====================================
Central state machine that routes user requests to the correct agent
(Portfolio, FIRE, Tax, or Couple) and handles the full lifecycle:
intent classification → profile validation → agent execution →
response synthesis → error recovery.

File: agents/orchestrator.py
Branch: feature/agents
"""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from state import FinSaarthiState, create_initial_state
from tools.audit_logger import AuditLogger

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.portfolio_agent import PortfolioAgent
from agents.fire_agent import FIREAgent
from agents.tax_agent import TaxAgent
from agents.couple_agent import CoupleAgent

# ── Optional: LangGraph SQLite checkpointer ──────────────────────────────────
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    _HAS_CHECKPOINTER = True
except ImportError:
    _HAS_CHECKPOINTER = False

# ── Optional: Gemini LLM ─────────────────────────────────────────────────────
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    _HAS_LLM = True
except ImportError:
    _HAS_LLM = False

# ── Optional: RAG ────────────────────────────────────────────────────────────
try:
    from rag.knowledge_base import FinancialKnowledgeBase
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False

load_dotenv()
logger = logging.getLogger("finsaarthi.orchestrator")

# ── Shared singletons (created once, reused across invocations) ──────────────
_audit_logger = AuditLogger(session_id="orchestrator-default")
_llm = None
_knowledge_base = None


def _get_llm():
    """Lazily initialize the Gemini LLM singleton."""
    global _llm
    if _llm is None and _HAS_LLM:
        _llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro"),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
            max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192")),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        )
    return _llm


def _get_kb():
    """Lazily initialize the RAG knowledge base singleton."""
    global _knowledge_base
    if _knowledge_base is None and _HAS_RAG:
        _knowledge_base = FinancialKnowledgeBase()
    return _knowledge_base


# ==============================================================================
# REQUIRED FIELDS PER MODULE (for profile validation)
# ==============================================================================

REQUIRED_FIELDS: Dict[str, Dict[str, list]] = {
    "portfolio": {
        "user_profile": ["risk_tolerance"],
        "root": ["uploaded_file_path"],
    },
    "fire": {
        "user_profile": ["age", "annual_income", "monthly_expenses"],
    },
    "tax": {
        # Either uploaded_file_path OR manual tax inputs
        "user_profile": ["annual_income"],
    },
    "couple": {
        "couple_data": ["partner_a_profile", "partner_b_profile"],
    },
}


# ==============================================================================
# NODE FUNCTIONS — Each takes FinSaarthiState, returns partial state update
# ==============================================================================

def classify_intent_node(state: FinSaarthiState) -> Dict[str, Any]:
    """
    Resolve user intent from module_selected.

    Parameters:
        state: Current graph state.

    Returns:
        Dict with intent and audit log update.
    """
    module = state.get("module_selected", "")
    valid_modules = {"portfolio", "fire", "tax", "couple"}
    intent = module if module in valid_modules else "unknown"

    _audit_logger.log("orchestrator", "classify_intent",
                      input_summary=f"module_selected: {module}",
                      output_summary=f"intent: {intent}")

    return {"intent": intent, "error_message": "" if intent != "unknown" else f"Unknown module: {module}"}


def collect_profile_node(state: FinSaarthiState) -> Dict[str, Any]:
    """
    Validate that all required fields for the selected module are present.

    Parameters:
        state: Current graph state.

    Returns:
        Dict with needs_more_input and missing_fields if validation fails.
    """
    intent = state.get("intent", "")
    requirements = REQUIRED_FIELDS.get(intent, {})
    missing: list = []

    # Check user_profile fields
    profile = state.get("user_profile", {})
    for field in requirements.get("user_profile", []):
        if not profile.get(field):
            missing.append(f"user_profile.{field}")

    # Check root-level fields
    for field in requirements.get("root", []):
        if not state.get(field):
            missing.append(field)

    # Check nested data fields
    for key in ("couple_data", "fire_data", "tax_data"):
        for field in requirements.get(key, []):
            data = state.get(key, {})
            if not data.get(field):
                missing.append(f"{key}.{field}")

    needs_input = len(missing) > 0

    _audit_logger.log("orchestrator", "validate_profile",
                      input_summary=f"Module: {intent}, fields checked: {len(requirements)}",
                      output_summary=f"Missing: {missing}" if missing else "All fields present")

    return {"needs_more_input": needs_input, "missing_fields": missing}


def portfolio_analysis_node(state: FinSaarthiState) -> Dict[str, Any]:
    """Run Portfolio X-Ray agent."""
    _audit_logger.log("orchestrator", "routing", output_summary="→ portfolio_agent")
    try:
        agent = PortfolioAgent(llm=_get_llm(), knowledge_base=_get_kb(), audit_logger=_audit_logger)
        pdf_path = state.get("uploaded_file_path", "")
        risk = state.get("user_profile", {}).get("risk_tolerance", "moderate")
        results = agent.analyze(pdf_path, risk)

        return {
            "agent_results": {**state.get("agent_results", {}), "portfolio": results},
            "portfolio_data": results.get("portfolio_summary", {}),
            "error_message": results.get("error_message", ""),
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        _audit_logger.log("orchestrator", "portfolio_failed", status="error", error_detail=str(e))
        return {"error_message": f"Portfolio analysis failed: {e}"}


def fire_planning_node(state: FinSaarthiState) -> Dict[str, Any]:
    """Run FIRE Path Planner agent."""
    _audit_logger.log("orchestrator", "routing", output_summary="→ fire_agent")
    try:
        agent = FIREAgent(llm=_get_llm(), knowledge_base=_get_kb(), audit_logger=_audit_logger)
        profile = state.get("user_profile", {})
        user_data = {
            "age": profile.get("age", 30),
            "monthly_income": profile.get("annual_income", 0) / 12,
            "monthly_expenses": profile.get("monthly_expenses", 0),
            "existing_investments": profile.get("existing_investments", 0),
            "risk_profile": profile.get("risk_tolerance", "moderate"),
            "target_retirement_age": state.get("fire_data", {}).get("target_retirement_age", 50),
            "goals": state.get("fire_data", {}).get("goal_breakdown", []),
            "existing_life_cover": 0,
            "existing_health_cover": 0,
            "existing_emis": 0,
        }
        results = agent.plan(user_data)

        return {
            "agent_results": {**state.get("agent_results", {}), "fire": results},
            "fire_data": {
                "fire_number": results.get("fire_number", {}).get("fire_corpus", 0),
                "monthly_sip_required": results.get("sip_feasibility", {}).get("total_sip_needed", 0),
                "year_wise_projection": results.get("year_wise_projection", []),
            },
            "error_message": results.get("error_message", ""),
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        _audit_logger.log("orchestrator", "fire_failed", status="error", error_detail=str(e))
        return {"error_message": f"FIRE planning failed: {e}"}


def tax_analysis_node(state: FinSaarthiState) -> Dict[str, Any]:
    """Run Tax Wizard agent."""
    _audit_logger.log("orchestrator", "routing", output_summary="→ tax_agent")
    try:
        agent = TaxAgent(llm=_get_llm(), knowledge_base=_get_kb(), audit_logger=_audit_logger)
        pdf_path = state.get("uploaded_file_path")
        profile = state.get("user_profile", {})

        if pdf_path:
            results = agent.analyze(form16_path=pdf_path)
        else:
            manual = {
                "gross_salary": profile.get("annual_income", 0),
                "basic": profile.get("annual_income", 0) * 0.4,
                "hra_received": profile.get("annual_income", 0) * 0.2,
                "rent_paid": 0, "city_type": profile.get("city", "metro"),
                "deductions_80c_used": 0, "deductions_80d_used": 0,
                "nps_used": 0, "home_loan_interest": 0, "other_deductions": 0,
            }
            results = agent.analyze(manual_inputs=manual)

        return {
            "agent_results": {**state.get("agent_results", {}), "tax": results},
            "tax_data": {
                "old_regime_tax": results.get("regime_comparison", {}).get("old_tax", 0),
                "new_regime_tax": results.get("regime_comparison", {}).get("new_tax", 0),
                "recommended_regime": results.get("regime_comparison", {}).get("recommended_regime", ""),
                "missed_deductions": results.get("missed_deductions", []),
            },
            "error_message": results.get("error_message", ""),
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        _audit_logger.log("orchestrator", "tax_failed", status="error", error_detail=str(e))
        return {"error_message": f"Tax analysis failed: {e}"}


def couple_optimization_node(state: FinSaarthiState) -> Dict[str, Any]:
    """Run Couple's Money Planner agent."""
    _audit_logger.log("orchestrator", "routing", output_summary="→ couple_agent")
    try:
        agent = CoupleAgent(llm=_get_llm(), knowledge_base=_get_kb(), audit_logger=_audit_logger)
        couple = state.get("couple_data", {})
        p1 = couple.get("partner_a_profile", {})
        p2 = couple.get("partner_b_profile", {})
        goals = couple.get("joint_goals", [])
        results = agent.optimize(p1, p2, goals)

        return {
            "agent_results": {**state.get("agent_results", {}), "couple": results},
            "couple_data": {
                **couple,
                "savings_vs_separate": results.get("total_optimization", {}).get("total_annual_tax_saving", 0),
                "joint_fire_number": results.get("net_worth", {}).get("retirement_target", 0),
            },
            "error_message": results.get("error_message", ""),
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        _audit_logger.log("orchestrator", "couple_failed", status="error", error_detail=str(e))
        return {"error_message": f"Couple optimization failed: {e}"}


def synthesize_response_node(state: FinSaarthiState) -> Dict[str, Any]:
    """
    Combine agent results into a final user-facing response.
    """
    intent = state.get("intent", "")
    results = state.get("agent_results", {})
    module_result = results.get(intent, {})

    # Use agent's own narrative/action plan if available
    final = (
        module_result.get("narrative")
        or module_result.get("action_plan")
        or module_result.get("rebalancing_plan")
        or module_result.get("final_response")
        or "Analysis complete. See detailed results."
    )

    # Add audit summary
    audit_summary = _audit_logger.get_session_summary()

    _audit_logger.log("orchestrator", "synthesize_response",
                      output_summary=f"Final response: {len(final)} chars, {audit_summary.get('total_actions', 0)} actions logged")

    now = datetime.now(timezone.utc).isoformat()
    return {"final_response": final, "last_updated_at": now}


def error_recovery_node(state: FinSaarthiState) -> Dict[str, Any]:
    """
    Attempt simplified analysis without LLM when errors occur.
    """
    error = state.get("error_message", "")
    intent = state.get("intent", "")

    _audit_logger.log("orchestrator", "error_recovery",
                      input_summary=f"Error: {error}", status="warning")

    recovery_msg = (
        f"## ⚠️ Partial Results Available\n\n"
        f"The {intent} analysis encountered an issue: *{error}*\n\n"
        f"**What happened:** The AI explanation module was unavailable, "
        f"but all financial calculations were completed successfully.\n\n"
        f"**Your data is safe.** Please try again or contact support."
    )

    return {"final_response": recovery_msg, "error_message": ""}


# ==============================================================================
# ROUTING LOGIC
# ==============================================================================

def _route_after_validation(state: FinSaarthiState) -> str:
    """
    Conditional edge: if fields are missing, go to END.
    Otherwise route to the correct agent node.
    """
    if state.get("needs_more_input", False):
        return "end"

    intent = state.get("intent", "")
    route_map = {
        "portfolio": "portfolio_analysis",
        "fire": "fire_planning",
        "tax": "tax_analysis",
        "couple": "couple_optimization",
    }
    return route_map.get(intent, "error_recovery")


def _route_after_agent(state: FinSaarthiState) -> str:
    """After any agent node: go to synthesize or error recovery."""
    if state.get("error_message"):
        return "error_recovery"
    return "synthesize_response"


# ==============================================================================
# GRAPH BUILDER
# ==============================================================================

def build_graph(session_id: str = "default") -> Any:
    """
    Build and compile the FinSaarthi LangGraph state machine.

    Architecture:
        START → classify_intent → collect_profile → [conditional routing]
            ├─ portfolio_analysis ──┐
            ├─ fire_planning ───────┤
            ├─ tax_analysis ────────┼─→ synthesize_response → END
            ├─ couple_optimization ─┘
            └─ error_recovery ──────────→ END

    Parameters:
        session_id (str): Session ID for audit logging and checkpointing.

    Returns:
        Compiled LangGraph StateGraph ready for .invoke().
    """
    global _audit_logger
    _audit_logger = AuditLogger(session_id=session_id)

    # ── Build the graph ───────────────────────────────────────────────────
    workflow = StateGraph(FinSaarthiState)

    # Add all nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("collect_profile", collect_profile_node)
    workflow.add_node("portfolio_analysis", portfolio_analysis_node)
    workflow.add_node("fire_planning", fire_planning_node)
    workflow.add_node("tax_analysis", tax_analysis_node)
    workflow.add_node("couple_optimization", couple_optimization_node)
    workflow.add_node("synthesize_response", synthesize_response_node)
    workflow.add_node("error_recovery", error_recovery_node)

    # ── Edges ─────────────────────────────────────────────────────────────
    # START → classify → validate
    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "collect_profile")

    # Conditional: validate → agent OR end
    workflow.add_conditional_edges(
        "collect_profile",
        _route_after_validation,
        {
            "portfolio_analysis": "portfolio_analysis",
            "fire_planning": "fire_planning",
            "tax_analysis": "tax_analysis",
            "couple_optimization": "couple_optimization",
            "error_recovery": "error_recovery",
            "end": END,
        },
    )

    # Agent → synthesize or error
    for agent_node in ("portfolio_analysis", "fire_planning", "tax_analysis", "couple_optimization"):
        workflow.add_conditional_edges(
            agent_node,
            _route_after_agent,
            {"synthesize_response": "synthesize_response", "error_recovery": "error_recovery"},
        )

    # Terminal edges
    workflow.add_edge("synthesize_response", END)
    workflow.add_edge("error_recovery", END)

    # ── Compile with optional checkpointer ────────────────────────────────
    compile_kwargs = {}
    if _HAS_CHECKPOINTER:
        try:
            db_path = os.getenv("AUDIT_DB_PATH", "./data/finsaarthi_audit.db")
            checkpointer = SqliteSaver.from_conn_string(db_path.replace(".db", "_checkpoints.db"))
            compile_kwargs["checkpointer"] = checkpointer
            logger.info(f"LangGraph checkpointer enabled: {db_path}")
        except Exception as e:
            logger.warning(f"Checkpointer init failed, running without: {e}")

    compiled = workflow.compile(**compile_kwargs)
    _audit_logger.log("orchestrator", "graph_compiled", output_summary="LangGraph state machine ready")

    return compiled


# ==============================================================================
# CONVENIENCE RUNNER
# ==============================================================================

def run_module(
    module: str,
    user_profile: Dict[str, Any] = None,
    uploaded_file_path: str = None,
    fire_data: Dict[str, Any] = None,
    tax_data: Dict[str, Any] = None,
    couple_data: Dict[str, Any] = None,
    session_id: str = None,
) -> Dict[str, Any]:
    """
    High-level convenience function to run a single module end-to-end.

    Usage:
        from agents.orchestrator import run_module
        result = run_module(
            module="tax",
            user_profile={"annual_income": 1200000, "city": "metro"},
            session_id="demo-001",
        )
        print(result["final_response"])

    Parameters:
        module (str): "portfolio" | "fire" | "tax" | "couple".
        user_profile (dict): User demographic/financial data.
        uploaded_file_path (str): Path to uploaded PDF.
        fire_data (dict): FIRE-specific inputs.
        tax_data (dict): Tax-specific inputs.
        couple_data (dict): Couple-specific inputs.
        session_id (str): Unique session identifier.

    Returns:
        Dict: Final state after graph execution.
    """
    import uuid

    sid = session_id or str(uuid.uuid4())
    graph = build_graph(session_id=sid)
    state = create_initial_state(module=module, session_id=sid)

    # Populate state with provided data
    if user_profile:
        state["user_profile"] = user_profile
    if uploaded_file_path:
        state["uploaded_file_path"] = uploaded_file_path
    if fire_data:
        state["fire_data"] = fire_data
    if tax_data:
        state["tax_data"] = tax_data
    if couple_data:
        state["couple_data"] = couple_data

    # Run the graph
    config = {"configurable": {"thread_id": sid}}
    final_state = graph.invoke(state, config=config)

    return final_state
