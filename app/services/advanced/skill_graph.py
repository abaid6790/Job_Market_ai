"""
Skill relationship graph.

Builds a node/edge graph directly from Phase 5's real co-occurrence data
(which skills appear together in the same job posting). Nothing here is
inferred or predicted — an edge exists only if those two skills genuinely
appeared together in at least MIN_EDGE_WEIGHT analyzed postings.

Like every analytics feature in this app, it reports insufficient data
honestly rather than rendering a sparse or misleading graph.
"""
from app.services.market.analytics import skill_cooccurrence, skill_demand, total_jobs_analyzed

MIN_JOBS_FOR_GRAPH = 3
MIN_EDGE_WEIGHT = 2
MAX_NODES = 40
MAX_EDGES = 80


def build_skill_graph(limit_nodes=MAX_NODES):
    total = total_jobs_analyzed()
    if total < MIN_JOBS_FOR_GRAPH:
        return {
            "available": False,
            "reason": (
                f"Insufficient data — a skill graph needs at least "
                f"{MIN_JOBS_FOR_GRAPH} analyzed jobs to show meaningful "
                f"relationships (currently {total})."
            ),
        }

    demand = skill_demand(limit=limit_nodes)
    if not demand:
        return {"available": False, "reason": "No skills detected in the analyzed jobs yet."}

    node_ids = {d["skill"].id for d in demand}
    nodes = [
        {
            "id": d["skill"].id,
            "name": d["skill"].name,
            "category": d["skill"].category.name if d["skill"].category else "Uncategorized",
            "demand_pct": d["percentage"],
            "job_count": d["count"],
        }
        for d in demand
    ]

    edges = []
    for pair in skill_cooccurrence(limit=500):
        if pair["count"] < MIN_EDGE_WEIGHT:
            continue
        a_id, b_id = pair["skill_a"].id, pair["skill_b"].id
        # Only draw edges between skills that are actually on the graph.
        if a_id in node_ids and b_id in node_ids:
            edges.append({"source": a_id, "target": b_id, "weight": pair["count"]})
        if len(edges) >= MAX_EDGES:
            break

    if not edges:
        return {
            "available": False,
            "reason": (
                "Skills were detected, but no two skills have yet appeared together in "
                f"{MIN_EDGE_WEIGHT}+ of the same job postings — so there are no real "
                "relationships to draw. Analyze more jobs to build this up."
            ),
        }

    # Drop isolated nodes so the graph doesn't render a field of
    # disconnected dots that imply "no relationships" when really those
    # skills just weren't co-mentioned often enough.
    connected = {e["source"] for e in edges} | {e["target"] for e in edges}
    nodes = [n for n in nodes if n["id"] in connected]

    return {
        "available": True,
        "total_jobs": total,
        "nodes": nodes,
        "edges": edges,
        "min_edge_weight": MIN_EDGE_WEIGHT,
    }
