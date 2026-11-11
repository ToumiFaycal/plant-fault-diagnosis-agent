"""Search the plant's reference documents (knowledge/) by meaning, not by exact words.

The idea, in three steps:
  1. Cut the two documents into sections (one per "## " heading).
  2. Turn each section into a list of 768 numbers that captures what it means (an "embedding"),
     with the embeddinggemma model run by Ollama. Texts with close meanings get close lists, even
     with different words ("cooling water valve sticks" is close to "the valve ... sticks").
     This is done once and saved, like the monitor.
  3. To search, turn the question into its own list of numbers the same way, and keep the
     sections whose lists point in the most similar direction (cosine similarity).

Build (or rebuild after editing knowledge/) the saved index, and see example searches:
    python -m plantagent.docsearch
"""

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import ollama

from plantagent.config import PROJECT_ROOT, load_config

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
KNOWLEDGE_FILES = ("process_overview.md", "fault_catalogue.md")  # README.md is about the files, not the plant
SKIPPED_SECTIONS = ("Sources",)  # where the facts came from: useful to people, noise for a search


@dataclass(frozen=True)
class Section:
    section_id: str  # like "fault_catalogue#fault-5": the file, then the start of the heading
    title: str
    text: str


@dataclass
class DocIndex:
    """The sections, the meaning of each one (one row of numbers per section), and the way to turn
    a question into numbers. Tests give it made-up numbers and a made-up `embed_query`."""
    sections: list[Section]
    vectors: np.ndarray  # rows = sections, columns = 768 numbers
    embed_query: Callable[[str], np.ndarray] = field(repr=False)


# --- 1. Sections ---

def split_into_sections(file_stem: str, text: str) -> list[Section]:
    """One section per "## " heading. The text before the first heading (the document's own
    introduction) and the Sources section are left out."""
    sections = []
    for part in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = part.partition("\n")
        title = title.strip()
        if title in SKIPPED_SECTIONS:
            continue
        # A short, readable ID from the start of the heading: "Fault 5: condenser ..." -> "fault-5".
        slug = re.sub(r"[^a-z0-9]+", "-", title.split(":")[0].lower()).strip("-")
        sections.append(Section(section_id=f"{file_stem}#{slug}", title=title, text=body.strip()))
    return sections


def knowledge_sections() -> list[Section]:
    sections = []
    for name in KNOWLEDGE_FILES:
        path = KNOWLEDGE_DIR / name
        sections += split_into_sections(path.stem, path.read_text(encoding="utf-8"))
    return sections


def fingerprint(sections: list[Section]) -> str:
    """A short code that changes whenever any section changes, to notice a saved index that no
    longer matches the documents."""
    content = "\n".join(f"{s.section_id}\n{s.title}\n{s.text}" for s in sections)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# --- 2. Meanings as numbers (embeddings) ---
# embeddinggemma expects documents and questions written in a fixed form (from its model card):
#   document: "title: {title} | text: {text}"      question: "task: search result | query: {question}"

def embedding_model() -> str:
    return load_config()["docs"]["embedding_model"]


def embed_documents(sections: list[Section]) -> np.ndarray:
    texts = [f"title: {s.title} | text: {s.text}" for s in sections]
    # truncate=False: if a section were too long for the model, stop with an error instead of
    # silently cutting its end off.
    response = ollama.embed(model=embedding_model(), input=texts, truncate=False)
    return np.array(response.embeddings)


def embed_query(query: str) -> np.ndarray:
    response = ollama.embed(model=embedding_model(), input=f"task: search result | query: {query}")
    return np.array(response.embeddings[0])


# --- Saving and loading the index ---

def index_path() -> Path:
    return PROJECT_ROOT / load_config()["data"]["docs_index_file"]


def save_index(path: Path, sections: list[Section], vectors: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, section_ids=np.array([s.section_id for s in sections]), vectors=vectors,
             fingerprint=np.array(fingerprint(sections)))


def load_index(path: Path, sections: list[Section], embed: Callable[[str], np.ndarray] = embed_query) -> DocIndex:
    """The saved meanings, matched with today's sections. Refuses an index made from older text."""
    with np.load(path) as saved:
        if str(saved["fingerprint"]) != fingerprint(sections):
            raise ValueError("The documents in knowledge/ changed since the search index was built: "
                             "run  python -m plantagent.docsearch  again.")
        return DocIndex(sections=sections, vectors=saved["vectors"], embed_query=embed)


# --- 3. Searching ---

def cosine_similarities(query_vector: np.ndarray, section_vectors: np.ndarray) -> np.ndarray:
    """How close in meaning the question is to each section, between -1 and 1.

    Each list of numbers is an arrow. Cosine similarity compares only their directions, not their
    lengths: 1 = same direction (same meaning), 0 = at right angles (unrelated), -1 = opposite.
    Formula, for one section: (query . section) / (length of query x length of section),
    where "." is the dot product (multiply number by number, then add up) and a length is
    np.linalg.norm(arrow).

    query_vector: one arrow (768 numbers).  section_vectors: one arrow per row.
    Returns one similarity per section, in the same order as the rows.
    Example: query [3, 4] and sections [[1, 0], [0, 2], [-1, 0]] -> [0.6, 0.8, -0.6].
    """
    dot_products = section_vectors @ query_vector
    lengths = np.linalg.norm(section_vectors, axis=1)
    query_length = np.linalg.norm(query_vector)
    return dot_products / (lengths * query_length)


def search(index: DocIndex, query: str, results: int, cutoff: float) -> list[tuple[Section, float]]:
    """The `results` sections most similar to the question, best first, leaving out any below `cutoff`."""
    similarities = cosine_similarities(index.embed_query(query), index.vectors)
    best_first = np.argsort(similarities)[::-1][:results]
    return [(index.sections[i], float(similarities[i])) for i in best_first if similarities[i] >= cutoff]


EXAMPLE_QUESTIONS = (
    "reactor cooling water",
    "condenser cooling water valve sticks",
    "what does the product stripper do",
    "why do composition analysers update slowly",
    "loss of the A feed",
    "how to bake bread",  # unrelated: nothing should pass the cutoff
)


def main() -> None:
    sections = knowledge_sections()
    print(f"{len(sections)} sections from {', '.join(KNOWLEDGE_FILES)}. Computing their meanings with "
          f"{embedding_model()} (the first call also loads the model)...")
    vectors = embed_documents(sections)
    path = index_path()
    save_index(path, sections, vectors)
    print(f"Saved the search index to {path.relative_to(PROJECT_ROOT)}: {vectors.shape[0]} sections x "
          f"{vectors.shape[1]} numbers.")

    settings = load_config()["docs"]
    index = load_index(path, sections)
    print(f"\nExample searches (best {settings['results']} sections, cutoff {settings['cutoff']}):")
    for question in EXAMPLE_QUESTIONS:
        similarities = cosine_similarities(index.embed_query(question), index.vectors)
        found = search(index, question, settings["results"], settings["cutoff"])
        shown = ", ".join(f"{section.section_id} {similarity:.2f}" for section, similarity in found) or "nothing"
        print(f"  {question!r}: {shown}   (best of all: {similarities.max():.2f})")


if __name__ == "__main__":
    main()
