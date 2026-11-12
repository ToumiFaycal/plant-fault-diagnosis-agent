"""Tests for the document search: cutting the documents into sections, comparing meanings, ranking,
and the saved index."""

import numpy as np
import ollama
import pytest

from plantagent.config import load_config
from plantagent.docsearch import (DocIndex, Section, cosine_similarities, index_path, knowledge_sections, load_index,
                                  save_index, search, split_into_sections)

MADE_UP_DOCUMENT = """# A made-up document

An introduction, which is left out.

## Fault 5: the condenser gets warmer

- **What changes:** the cooling water.

## The reactor

Where the reactions happen.

## Sources

- Somewhere.
"""


def made_up_index() -> DocIndex:
    """Three sections whose "meanings" are arrows along three different directions, and a made-up
    way to turn a question into an arrow (a 4th direction stands for "something else")."""
    sections = [Section(f"doc#{name}", name.title(), f"About the {name}.") for name in ("reactor", "condenser", "stripper")]
    questions = {"mostly the reactor": [0.8, 0.6, 0.0, 0.0],  # similarities 0.8, 0.6 and 0
                 "something else": [0.0, 0.0, 0.0, 1.0]}       # similar to nothing
    return DocIndex(sections=sections, vectors=np.eye(4)[:3], embed_query=lambda query: np.array(questions[query]))


# --- Sections ---

def test_one_section_per_heading_without_the_intro_or_the_sources():
    sections = split_into_sections("doc", MADE_UP_DOCUMENT)
    assert [section.section_id for section in sections] == ["doc#fault-5", "doc#the-reactor"]
    assert sections[0].title == "Fault 5: the condenser gets warmer"
    assert sections[1].text == "Where the reactions happen."


def test_the_real_documents_have_one_section_per_catalogue_fault():
    sections = knowledge_sections()
    ids = [section.section_id for section in sections]
    assert len(ids) == len(set(ids))  # each ID points to one section only
    for fault in range(1, 16):
        assert f"fault_catalogue#fault-{fault}" in ids
    assert "fault_catalogue#faults-16-to-20" in ids
    assert all(section.text for section in sections)


def test_the_agent_can_only_search_the_two_knowledge_documents():
    # docs/DECISIONS.md, the README and the results name the true faults of development episodes:
    # the agent must never be able to read them.
    documents = {section.section_id.split("#")[0] for section in knowledge_sections()}
    assert documents == {"process_overview", "fault_catalogue"}


# --- Comparing meanings (cosine_similarities is yours) ---

def test_cosine_similarity_of_simple_arrows():
    similarities = cosine_similarities(np.array([3.0, 4.0]), np.array([[1.0, 0.0], [0.0, 2.0], [-1.0, 0.0]]))
    assert np.allclose(similarities, [0.6, 0.8, -0.6])


def test_cosine_similarity_ignores_length():
    # Same direction, different lengths: the same meaning.
    similarities = cosine_similarities(np.array([1.0, 1.0]), np.array([[5.0, 5.0], [0.1, 0.1]]))
    assert np.allclose(similarities, [1.0, 1.0])


# --- Ranking ---

def test_search_gives_the_most_similar_first_and_leaves_out_the_rest():
    found = search(made_up_index(), "mostly the reactor", results=3, cutoff=0.35)
    assert [(section.section_id, round(similarity, 3)) for section, similarity in found] == [("doc#reactor", 0.8),
                                                                                           ("doc#condenser", 0.6)]
    assert len(search(made_up_index(), "mostly the reactor", results=1, cutoff=0.35)) == 1


def test_search_can_find_nothing():
    assert search(made_up_index(), "something else", results=3, cutoff=0.35) == []


# --- The saved index ---

def test_the_saved_index_comes_back_and_refuses_edited_documents(tmp_path):
    index = made_up_index()
    save_index(tmp_path / "index.npz", index.sections, index.vectors)
    loaded = load_index(tmp_path / "index.npz", index.sections, embed=index.embed_query)
    assert np.allclose(loaded.vectors, index.vectors)

    edited = [Section("doc#reactor", "Reactor", "The text was edited.")] + index.sections[1:]
    with pytest.raises(ValueError):  # the saved meanings belong to the old text
        load_index(tmp_path / "index.npz", edited)


def ollama_is_running() -> bool:
    try:
        ollama.list()
        return True
    except ConnectionError:
        return False


@pytest.mark.skipif(not (index_path().exists() and ollama_is_running()),
                    reason="needs the saved search index and Ollama (never on GitHub)")
def test_a_real_search_finds_the_right_section():
    settings = load_config()["docs"]
    index = load_index(index_path(), knowledge_sections())
    found = search(index, "what does the product stripper do", settings["results"], settings["cutoff"])
    assert found[0][0].section_id == "process_overview#the-product-stripper"
    assert search(index, "how to bake bread", settings["results"], settings["cutoff"]) == []
