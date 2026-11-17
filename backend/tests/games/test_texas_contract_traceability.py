"""P3-05: the written Texas hold'em contract is tied to real tests.

docs/TEXAS_HOLDEM_CONTRACT.md lists every rule as a clause with a source and a status. These
tests parse that table and refuse a contract that points at tests that do not exist, claims
tests for a rule that is still an open policy, or silently drops a required topic. They do not
prove the rules are right: a clause's status says who decided it, the referenced tests say the
code follows it.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parent
CONTRACT = ROOT / "docs" / "TEXAS_HOLDEM_CONTRACT.md"
STATUSES = {"SPEC", "APPROVED", "CHOSEN", "OPEN"}
ROW = re.compile(r"^\|\s*(R\d+\.\d+)\s*\|(.*)\|\s*$")

# Every topic the contract must cover, mapped to clauses that must exist for it.
REQUIRED = {
    "deck and card legality": ["R1.1", "R1.3"],
    "players and seats": ["R2.1", "R2.2"],
    "dealer button": ["R3.1", "R3.3"],
    "small and big blind": ["R3.2", "R3.4", "R3.5"],
    "burn cards": ["R4.1", "R4.2"],
    "pre-flop, flop, turn, river, showdown": ["R5.1"],
    "fold, check, call, bet, raise, all-in": ["R6.1", "R6.3", "R6.5"],
    "main and side pots": ["R7.1"],
    "return of the uncalled amount": ["R7.1"],
    "merging of layers": ["R7.2"],
    "ties and odd chips": ["R7.3", "R7.4"],
    "competition rank": ["R8.2"],
    "showdown reveal": ["R8.1"],
    "settlement result and chip conservation": ["R7.8", "R9.4"],
    "settlement application and duplicate guard": ["R9.2", "R9.3"],
    "registry": ["R11.1", "R11.2", "R11.3"],
}


def clauses() -> list[tuple[str, str, str, str, str]]:
    rows = []
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(2).split("|")]
        assert len(cells) == 4, f"clause {match.group(1)} must have clause, source, status, tests"
        rows.append((match.group(1), cells[0], cells[1], cells[2], cells[3]))
    return rows  # (id, clause, source, status, tests)


def module_tests(file_name: str) -> set[str]:
    path = TESTS / file_name
    if not path.exists():
        path = TESTS.parent / file_name
    assert path.exists(), f"test file {file_name} does not exist"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def test_the_contract_table_exists_and_has_unique_ids_and_valid_statuses() -> None:
    rows = clauses()
    assert len(rows) >= 40
    ids = [row[0] for row in rows]
    assert len(ids) == len(set(ids)), "duplicate clause ids"
    for clause_id, text, source, status, _ in rows:
        assert status in STATUSES, (clause_id, status)
        assert text and source, clause_id


def test_every_clause_that_is_not_open_points_at_tests_that_really_exist() -> None:
    for clause_id, _, _, status, tests in clauses():
        if status == "OPEN":
            continue
        refs = [ref.strip() for ref in tests.split(";") if ref.strip()]
        assert refs and tests != "none", f"{clause_id} ({status}) has no test"
        for ref in refs:
            file_name, _, name = ref.partition("::")
            assert name, f"{clause_id}: '{ref}' is not file::test"
            assert name in module_tests(file_name), f"{clause_id}: {ref} does not exist"


def test_an_open_policy_never_claims_tests_or_a_rule() -> None:
    open_rows = [row for row in clauses() if row[3] == "OPEN"]
    assert {row[0] for row in open_rows} >= {"R2.5", "R3.4", "R4.1", "R9.7"}
    for clause_id, _, source, _, tests in open_rows:
        assert tests == "none", f"{clause_id} is OPEN and must not claim tests"
        assert source, clause_id


def test_every_required_topic_is_covered_by_the_contract() -> None:
    present = {row[0] for row in clauses()}
    for topic, needed in REQUIRED.items():
        missing = [clause for clause in needed if clause not in present]
        assert not missing, f"contract does not cover {topic}: {missing}"


def test_chosen_and_open_clauses_are_never_dressed_up_as_specification() -> None:
    by_id = {row[0]: row for row in clauses()}
    for clause_id in ("R1.4", "R3.2", "R3.3", "R7.2", "R7.4", "R8.1", "R8.2", "R9.2"):
        assert by_id[clause_id][3] == "CHOSEN", clause_id
    for clause_id in ("R2.5", "R3.4", "R4.1", "R9.7"):
        assert by_id[clause_id][3] == "OPEN", clause_id
    for clause_id in ("R7.1", "R7.3", "R7.6", "R7.8"):
        assert by_id[clause_id][3] == "SPEC", clause_id


def test_the_policy_review_names_all_five_unconfirmed_policies() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for heading in ("政策 1", "政策 2", "政策 3", "政策 4", "政策 5"):
        assert heading in text
    for label in ("既有依據", "缺口", "候選", "程式影響", "是否阻擋"):
        assert text.count(label) >= 5, label


@pytest.mark.parametrize("clause_id", ["R9.2", "R9.3", "R9.6"])
def test_the_new_settlement_clauses_name_this_phase_as_their_source(clause_id: str) -> None:
    row = next(row for row in clauses() if row[0] == clause_id)
    assert "P3-05" in row[2]
