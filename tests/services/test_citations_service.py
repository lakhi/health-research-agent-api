"""Unit tests for services.citations_service."""

import json

from services.citations_service import build_citations, extract_excerpt, format_citations_sse


class TestExtractExcerpt:
    def test_short_content_returned_as_is(self):
        content = "Bachelor Psychologie deadline is March 15."
        out = extract_excerpt(content, query="bachelor", max_chars=200)
        assert out == content
        assert "…" not in out

    def test_window_centered_on_keyword(self):
        prefix = "lorem ipsum " * 30
        suffix = " trailing context " * 30
        content = prefix + "BACHELOR registration opens in May" + suffix
        out = extract_excerpt(content, query="bachelor", max_chars=80)
        assert "BACHELOR" in out
        assert out.startswith("…")
        assert out.endswith("…")

    def test_no_keyword_match_falls_back_to_leading_window(self):
        content = "Alpha beta gamma delta epsilon zeta eta theta " * 20
        out = extract_excerpt(content, query="nonexistentword", max_chars=60)
        assert out.startswith("Alpha")
        assert out.endswith("…")
        assert not out.startswith("…")

    def test_collapses_internal_whitespace(self):
        content = "foo\n\n\nbar   \t  baz BACHELOR qux\n\nquux"
        out = extract_excerpt(content, query="bachelor", max_chars=200)
        assert "  " not in out
        assert "\n" not in out
        assert "\t" not in out

    def test_empty_content(self):
        assert extract_excerpt("", query="anything") == ""

    def test_stopwords_ignored_when_picking_keyword(self):
        prefix = "filler " * 50
        content = prefix + "WICHTIG admission requirements section"
        # "the" and "of" are stopwords; "admission" should drive windowing.
        out = extract_excerpt(content, query="the admission of", max_chars=80)
        assert "admission" in out.lower()


class TestBuildCitations:
    def _chunk(self, source_url: str | None, content: str = "x", **meta) -> dict:
        meta_data = {"source_url": source_url, **meta} if source_url else dict(meta)
        return {"name": meta.get("page_title", "doc"), "meta_data": meta_data, "content": content}

    def _refs(self, *chunks) -> list:
        """Wrap chunks in a single MessageReferences-shaped dict."""
        return [{"query": "test", "references": list(chunks), "time": 0.01}]

    def test_empty_references_returns_empty(self):
        assert build_citations(None, query="anything") == []
        assert build_citations([], query="anything") == []

    def test_skips_chunks_without_source_url(self):
        refs = self._refs(
            self._chunk(None, content="no url"),
            self._chunk(None, content="also no url"),
        )
        assert build_citations(refs, query="x") == []

    def test_dedup_first_seen_per_url(self):
        url = "https://ssc-psychologie.univie.ac.at/studium/bachelor/"
        refs = self._refs(
            self._chunk(
                url, content="first chunk content", page_title="Bachelor", source_type="web_page", language="de"
            ),
            self._chunk(
                url, content="second chunk content", page_title="Bachelor", source_type="web_page", language="de"
            ),
        )
        out = build_citations(refs, query="bachelor")
        assert len(out) == 1
        assert "first chunk" in out[0]["excerpt"]

    def test_metadata_mapping(self):
        url = "https://ssc-psychologie.univie.ac.at/downloads/form.pdf"
        refs = self._refs(
            self._chunk(
                url,
                content="Application form text body.",
                document_title="Application Form",
                source_type="pdf_document",
                language="en",
            )
        )
        out = build_citations(refs, query="application")
        assert len(out) == 1
        c = out[0]
        assert c["source_url"] == url
        assert c["title"] == "Application Form"
        assert c["source_type"] == "pdf_document"
        assert c["language"] == "en"
        assert "Application" in c["excerpt"]
        assert c["score"] == 1.0

    def test_default_language_when_missing(self):
        url = "https://ssc-psychologie.univie.ac.at/downloads/x.pdf"
        refs = self._refs(self._chunk(url, content="text", source_type="pdf_document"))
        out = build_citations(refs, query="x")
        assert out[0]["language"] == "de"

    def test_score_decreases_with_rank(self):
        refs = self._refs(
            self._chunk("https://a.example/", content="a"),
            self._chunk("https://b.example/", content="b"),
            self._chunk("https://c.example/", content="c"),
        )
        out = build_citations(refs, query="x")
        scores = [c["score"] for c in out]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 1.0
        assert scores[-1] < 1.0

    def test_flattens_multiple_message_references(self):
        url_a = "https://a.example/"
        url_b = "https://b.example/"
        refs = [
            {"query": "q1", "references": [self._chunk(url_a, content="aa")], "time": 0.01},
            {"query": "q2", "references": [self._chunk(url_b, content="bb")], "time": 0.01},
        ]
        out = build_citations(refs, query="x")
        assert {c["source_url"] for c in out} == {url_a, url_b}


class TestFormatCitationsSse:
    """The agent-ui stream parser drops SSE framing lines and routes on the
    `event` key inside the data JSON — these tests pin that contract."""

    def test_event_key_embedded_in_payload(self):
        citations = [{"source_url": "https://a.example/", "excerpt": "x", "score": 1.0}]
        frame = format_citations_sse(citations)
        assert frame.startswith("event: Citations\ndata: ")
        assert frame.endswith("\n\n")
        payload = json.loads(frame.split("data: ", 1)[1])
        assert payload["event"] == "Citations"
        assert payload["citations"] == citations

    def test_empty_citations_still_carries_event_key(self):
        frame = format_citations_sse([])
        payload = json.loads(frame.split("data: ", 1)[1])
        assert payload == {"event": "Citations", "citations": []}
