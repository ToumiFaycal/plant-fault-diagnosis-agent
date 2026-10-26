"""Tests for the plant's reference documents in knowledge/."""

import pandas as pd

from plantagent.config import PROJECT_ROOT

TAGS_CSV = PROJECT_ROOT / "knowledge" / "tags.csv"


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
