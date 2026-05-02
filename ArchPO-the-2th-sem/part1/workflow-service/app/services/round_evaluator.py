from __future__ import annotations
"""
Pure function: no DB, no HTTP, easily unit-testable.

evaluate_round returns:
  "approved"  — both sides approved
  "rejected"  — at least one side rejected (reject > revision > approve)
  "revision"  — at least one side wants revision (both decided, no reject)
  None        — waiting for more decisions (not all required sides have decided)
"""


def evaluate_round(decisions: list, approval_type: str) -> str | None:
    """
    Determine the outcome of a round given the list of decisions.

    decisions: list of objects with .decision_type (str) and .user_side (str).
    approval_type: "tz_final" | "nmck_final" | "review".

    Returns outcome string or None if round is still open.
    """
    if approval_type == "review":
        # review-type requests never close a round
        return None

    # Only non-review decisions count toward round closure
    final_decisions = [d for d in decisions if d.decision_type != "review"]

    if approval_type not in ("tz_final", "nmck_final"):
        return None

    required_sides = {"customer", "contractor"}
    decided_sides = {d.user_side for d in final_decisions}

    if decided_sides != required_sides:
        return None  # still waiting for the other side

    # Priority: reject > revision > approve
    if any(d.decision_type == "reject" for d in final_decisions):
        return "rejected"
    if any(d.decision_type == "revision" for d in final_decisions):
        return "revision"
    return "approved"
