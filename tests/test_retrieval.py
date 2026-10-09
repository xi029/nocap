from nocap.retrieval import chunks, retrieve, tokenize


def test_multilingual_retrieval_and_stable_ids():
    docs = [
        {"id": "a", "name": "中文.md", "text": "本地部署默认端口是8080。"},
        {"id": "b", "name": "policy.md", "text": "Refund requests are accepted within 30 days."},
    ]
    found = retrieve(docs, "本地部署端口是多少？", 2)
    assert found[0].document_id == "a"
    assert found == retrieve(docs, "本地部署端口是多少？", 2)
    assert retrieve(docs, "lunar chess", 2) == []
    assert "部署" in tokenize("本地部署")


def test_long_paragraphs_do_not_exceed_chunk_limit():
    text = "word " * 700 + "\n\n中文" * 20
    assert all(len(chunk) <= 550 for chunk in chunks(text))
    assert chunks("  ") == []
