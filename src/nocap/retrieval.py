"""Small, transparent BM25 retrieval. No model download or vector service."""

import hashlib
import math
import re
from collections import Counter

from .models import Evidence

STOP = set(
    "a an the is are was were do does can how what when where which to of for in on and or i my we our it this that with from be me about have has many much".split()
)


def tokenize(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]
    for segment in re.findall(r"[\u3400-\u9fff]+", text):
        words.extend(segment[i : i + 2] for i in range(max(1, len(segment) - 1)))
    return words


def chunks(text: str, size: int = 550) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    result: list[str] = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if paragraph and all(line.lstrip().startswith("#") for line in paragraph.splitlines()):
            continue
        while len(paragraph) > size:
            cut = paragraph.rfind(" ", size // 2, size)
            cut = cut if cut > 0 else size
            result.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if paragraph:
            result.append(paragraph)
    return result


def retrieve(documents: list[dict], question: str, top_k: int) -> list[Evidence]:
    corpus: list[Evidence] = []
    for document in documents:
        for position, text in enumerate(chunks(document["text"])):
            digest = hashlib.sha256(f"{document['id']}:{position}:{text}".encode()).hexdigest()[:12]
            corpus.append(
                Evidence(
                    id=digest,
                    document_id=document["id"],
                    source=document["name"],
                    text=text,
                    score=0,
                    position=position,
                )
            )
    if not corpus:
        return []
    tokens = [Counter(tokenize(c.text)) for c in corpus]
    average = sum(sum(t.values()) for t in tokens) / len(tokens) or 1
    terms = set(tokenize(question))
    frequency = {term: sum(term in t for t in tokens) for term in terms}
    for chunk, counts in zip(corpus, tokens, strict=True):
        length = sum(counts.values())
        for term in terms:
            tf = counts[term]
            idf = math.log(1 + (len(corpus) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            chunk.score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        chunk.score = round(chunk.score, 4)
    return sorted((c for c in corpus if c.score > 0), key=lambda c: (-c.score, c.id))[:top_k]
