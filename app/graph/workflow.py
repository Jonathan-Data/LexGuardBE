"""
LexGuardBE compliance orchestration graph.

Routing
-------
    classifier ──┬──(prohibited)──▶ END
                 └──(else)─────────▶ auditor ──▶ END

The conditional edge ensures Article 5 systems bypass the Article 6(3)
auditor entirely — there is no "escape route" for prohibited practices,
and routing through the auditor would risk producing a misleading trail.
"""

from langgraph.graph import END, StateGraph

from app.graph.nodes import classifier_node, compliance_auditor
from app.models.state import AuditState


def _route_after_classifier(state: AuditState) -> str:
    """If Art. 5 fired, skip the Art. 6(3) auditor."""
    return "end" if state.get("is_prohibited") else "auditor"


def create_compliance_graph():
    workflow = StateGraph(AuditState)

    workflow.add_node("classifier", classifier_node)
    workflow.add_node("auditor", compliance_auditor)

    workflow.set_entry_point("classifier")
    workflow.add_conditional_edges(
        "classifier",
        _route_after_classifier,
        {"auditor": "auditor", "end": END},
    )
    workflow.add_edge("auditor", END)

    return workflow.compile()


# Compiled singleton — import this in the FastAPI handler.
compliance_engine = create_compliance_graph()
lexguard_graph = compliance_engine  # backward-compat alias
