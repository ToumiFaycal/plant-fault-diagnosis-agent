"""The fact-checker: checks every piece of evidence in a Diagnosis against the tool result it cites.

Each tool result carries a receipt number (call_id). Each piece of evidence names one. The
checker looks the receipt up among the calls really made in this investigation and checks that
the result says what the evidence claims:
  - the call_id exists (the model didn't invent a receipt);
  - it comes from the right tool for the claim (an above_normal claim must cite compare_to_normal);
  - the result really supports the claim (the tag is there, its z_score is far enough, the
    section was returned, the monitor did alarm).
Any problem is written as a sentence the model can act on, because the agent gets one chance to
fix its report (step 8.3).

See it on a real episode:
    python -m plantagent.agent.verifier
"""

from dataclasses import dataclass

from plantagent.agent.diagnosis import Diagnosis, Evidence

Z_THRESHOLD = 2.0  # the same rule as compare_to_normal's "up" / "down"

TOOL_FOR_CLAIM = {
    "above_normal": "compare_to_normal",
    "below_normal": "compare_to_normal",
    "top_contributor": "top_contributors",
    "monitor_alarm": "get_monitor_status",
    "doc_section": "search_docs",
}


@dataclass
class ToolCall:
    """One successful tool call of the investigation, as the agent received it."""
    call_id: str
    tool: str
    arguments: dict
    result: dict  # the result form, as a dict (structured_content)


@dataclass
class Verification:
    evidence_items: int
    failed_items: int
    problems: list[str]  # one sentence per problem; empty when everything holds

    @property
    def passed(self) -> bool:
        return not self.problems


# --- The individual checks ---

def z_supports_claim(claim: str, z_score: float) -> bool:
    """Does this z-score back the claim? "above_normal" needs z_score >= Z_THRESHOLD (2);
    "below_normal" needs z_score <= -Z_THRESHOLD. Examples: ("above_normal", 7.0) -> True,
    ("above_normal", 0.02) -> False, ("below_normal", -2.0) -> True, ("below_normal", 3.0) -> False.
    """
    if claim == "above_normal":
        return z_score >= Z_THRESHOLD
    if claim == "below_normal":
        return z_score <= -Z_THRESHOLD
    raise ValueError(f"Unexpected claim: {claim}")


def is_top_contributor(result: dict, tag: str) -> bool:
    """Is the tag among the signals a top_contributors result returned?
    The result looks like {"contributors": [{"rank": 1, "tag": "xmv_10", ...}, {"rank": 2, ...}]}."""
    return tag in [contributor["tag"] for contributor in result["contributors"]]


def section_was_returned(result: dict, section_id: str) -> bool:
    """Was this section returned by the search_docs result? The check that stops invented sources.
    The result looks like {"sections": [{"section_id": "fault_catalogue#fault-4", ...}, ...]}."""
    return section_id in [section["section_id"] for section in result["sections"]]


def find_signal(result: dict, tag: str) -> dict | None:
    """The entry for this tag in a compare_to_normal result, or None if the tag isn't there."""
    for signal in result["signals"]:
        if signal["tag"] == tag:
            return signal
    return None


# --- Putting the checks together ---

def check_evidence(item: Evidence, calls: dict[str, ToolCall]) -> list[str]:
    """The problems with one piece of evidence: an empty list means it holds."""
    call = calls.get(item.call_id)
    if call is None:
        return [f"no tool result has call_id {item.call_id}: cite only call_ids you received."]
    needed = TOOL_FOR_CLAIM[item.claim]
    if call.tool != needed:
        return [f"a {item.claim} claim must cite a {needed} result, but {item.call_id} is a {call.tool} result."]

    if item.claim == "monitor_alarm":
        if call.result["first_alarm_time"] is None:
            return [f"result {item.call_id} shows no alarm in its window: its first_alarm_time is null (a score "
                    f"above its limit for a moment is not an alarm)."]
        return []

    if item.claim == "doc_section":
        if item.section_id is None:
            return ["a doc_section claim needs the section_id it relies on."]
        if not section_was_returned(call.result, item.section_id):
            return [f"section {item.section_id} is not in result {item.call_id}."]
        return []

    # The three claims about one signal.
    if item.tag is None:
        return [f"a {item.claim} claim needs the tag it is about."]
    if item.claim == "top_contributor":
        if not is_top_contributor(call.result, item.tag):
            return [f"{item.tag} is not among the contributors in result {item.call_id}."]
        return []
    signal = find_signal(call.result, item.tag)
    if signal is None:
        return [f"{item.tag} is not in result {item.call_id}."]
    if not z_supports_claim(item.claim, signal["z_score"]):
        needed_z = "z_score >= 2" if item.claim == "above_normal" else "z_score <= -2"
        return [f"{item.tag} has z_score {signal['z_score']} in result {item.call_id}, so it is not "
                f"{item.claim.replace('_', ' ')} (that needs {needed_z})."]
    return []


def verify(diagnosis: Diagnosis, calls: dict[str, ToolCall]) -> Verification:
    """Check every piece of evidence of a diagnosis against the calls of its investigation."""
    problems, failed_items = [], 0
    if diagnosis.status == "fault" and not diagnosis.evidence:
        problems.append("a 'fault' diagnosis needs at least one piece of evidence.")
    for number, item in enumerate(diagnosis.evidence, start=1):
        item_problems = check_evidence(item, calls)
        if item_problems:
            failed_items += 1
            problems += [f"evidence {number} ({item.claim}, {item.call_id}): {problem}" for problem in item_problems]
    return Verification(evidence_items=len(diagnosis.evidence), failed_items=failed_items, problems=problems)


# --- Demo: a hand-written report checked against a real episode ---

def main() -> None:
    import asyncio
    import logging

    from mcp import Client

    from plantagent.docsearch import index_path, knowledge_sections, load_index
    from plantagent.mcp_server.episode import load_episode
    from plantagent.mcp_server.server import build_server
    from plantagent.monitor.saved import load_monitor, monitor_path

    logging.getLogger("httpx").setLevel(logging.WARNING)  # no line per search request to Ollama
    episode = load_episode("ep_f6f8d79c")
    server = build_server(episode, load_monitor(monitor_path()), load_index(index_path(), knowledge_sections()))
    asked = [("get_monitor_status", {"window_start": "00:00", "window_end": "09:09"}),
             ("top_contributors", {"window_start": "08:09", "window_end": "09:09", "k": 4, "statistic": "SPE"}),
             ("compare_to_normal", {"tags": ["xmeas_11", "xmeas_38"], "window_start": "08:09", "window_end": "09:09"}),
             ("search_docs", {"query": "condenser cooling water"})]

    async def investigate() -> dict[str, ToolCall]:
        calls = {}
        async with Client(server) as client:  # in memory: same tools, no separate program
            for tool, arguments in asked:
                result = (await client.call_tool(tool, arguments)).structured_content
                calls[result["call_id"]] = ToolCall(result["call_id"], tool, arguments, result)
        return calls

    calls = asyncio.run(investigate())
    print(f"Episode {episode.name}, now {episode.table['sample_time'].iloc[-1]}. Tool calls made:")
    for call in calls.values():
        print(f"  {call.call_id}: {call.tool}({call.arguments})")

    report = Diagnosis.model_validate({
        "evidence": [
            {"call_id": "c1", "claim": "monitor_alarm", "tag": None, "section_id": None,
             "detail": "The monitor alarmed."},
            {"call_id": "c2", "claim": "top_contributor", "tag": "xmeas_11", "section_id": None,
             "detail": "Separator temperature carries part of the strange pattern."},
            {"call_id": "c3", "claim": "above_normal", "tag": "xmeas_11", "section_id": None,
             "detail": "Separator temperature is above normal."},
            {"call_id": "c3", "claim": "above_normal", "tag": "xmeas_38", "section_id": None,
             "detail": "A big contributor, so surely above normal? (wrong on purpose)"},
            {"call_id": "c4", "claim": "doc_section", "tag": None, "section_id": "process_overview#the-condenser",
             "detail": "The condenser cools the reactor's vapour with cooling water."},
            {"call_id": "c9", "claim": "doc_section", "tag": None, "section_id": "fault_catalogue#fault-12",
             "detail": "A receipt that was never issued. (wrong on purpose)"},
        ],
        "key_variables": ["xmeas_11"], "affected_unit": None, "status": "inconclusive", "fault_id": None,
        "ranked_candidates": [], "confidence": "low", "recommended_checks": [],
    })
    print("\nChecking a hand-written report with 6 pieces of evidence (2 wrong on purpose):")
    for number, item in enumerate(report.evidence, start=1):
        problems = check_evidence(item, calls)
        verdict = "holds" if not problems else "FAILS: " + problems[0]
        about = " ".join(part for part in (item.claim, item.tag or item.section_id) if part)
        print(f"  {number}. {about} ({item.call_id}): {verdict}")
    verification = verify(report, calls)
    print(f"\n{verification.failed_items} of {verification.evidence_items} pieces of evidence failed; "
          f"passed = {verification.passed}.")


if __name__ == "__main__":
    main()
