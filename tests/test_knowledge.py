"""Tests for the plant's reference documents in knowledge/."""

import re

import pandas as pd
import pytest

from plantagent.config import PROJECT_ROOT

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
TAGS_CSV = KNOWLEDGE_DIR / "tags.csv"
FAULT_CATALOGUE = KNOWLEDGE_DIR / "fault_catalogue.md"


def test_every_cell_of_tags_csv_is_filled_in():
    tags = pd.read_csv(TAGS_CSV)
    empty_cells = tags.isna().sum().sum()  # count the empty cells in the whole table
    assert empty_cells == 0


def test_tags_match_the_data_columns_in_order():
    list_of_tags = list(pd.read_csv(TAGS_CSV)["tag"])
    expected_list = []
    for i in range(1, 42):
        expected_list.append(f"xmeas_{i}")
    for i in range(1, 12):
        expected_list.append(f"xmv_{i}")
    assert list_of_tags == expected_list


def test_every_signal_named_in_the_documents_exists():
    known_tags = set(pd.read_csv(TAGS_CSV)["tag"])
    for document in KNOWLEDGE_DIR.glob("*.md"):
        text = document.read_text(encoding="utf-8")
        named = set(re.findall(r"\b(?:xmeas|xmv)_\d+\b", text))  # every "xmeas_<number>" or "xmv_<number>"
        unknown = named - known_tags  # named in the document but missing from tags.csv
        assert unknown == set(), f"{document.name} names signals that don't exist: {sorted(unknown)}"


def test_fault_catalogue_has_one_section_per_described_fault():
    text = FAULT_CATALOGUE.read_text(encoding="utf-8")
    for fault in range(1, 16):
        assert f"## Fault {fault}:" in text, f"no section for fault {fault}"
    assert "## Faults 16 to 20" in text


def test_fault_catalogue_names_no_signals():
    catalogue_text = FAULT_CATALOGUE.read_text(encoding="utf-8")
    assert "xmeas_" not in catalogue_text
    assert "xmv_" not in catalogue_text
