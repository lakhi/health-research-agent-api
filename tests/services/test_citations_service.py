"""Unit tests for services.citations_service."""

import json

from services.citations_service import build_citations, extract_excerpt, format_citations_sse

# Abridged verbatim from the live "Informationen für Studienbeginner*innen" page —
# the chunk behind the Peer-Mentoring chip regression. The page header (which the
# excerpt must NOT quote) precedes the study-start content (which it should).
_STUDIENBEGINNER_CHUNK = (
    "Informationen für Studienbeginner*innen Herzlich willkommen an der "
    "Fakultät für Psychologie! Für Informationen zum Peer-Mentoring Psychologie "
    "hier klicken Anmeldung zu den Lehrveranstaltungen Folgende "
    "Lehrveranstaltungen sind für das erste Semester vorgesehen: die vier "
    "Vorlesungen der Studieneingangs- und Orientierungsphase (STEOP) - siehe "
    "unten die Vorlesung VO Allgemeine Psychologie I die Vorlesung VO "
    "Bildungspsychologie die Vorlesung und Übung VU Psychologische Forschung "
    "erleben und reflektieren Ausführliche Informationen über die Anmeldung zu "
    "Lehrveranstaltungen und Prüfungen finden Sie hier. Detaillierte "
    "Informationen zu allen Lehrveranstaltungen des Bachelorstudiums finden Sie "
    "im Curriculum sowie im Vorlesungsverzeichnis u:find. Studienbeginn im "
    "Sommersemester Sollten Sie im Sommersemester mit dem Bachelorstudium "
    "Psychologie beginnen, empfehlen wir Ihnen, sich für die STEOP-Vorlesungen "
    "aus dem vorhergehenden Wintersemester zu registrieren und sich den "
    "Lehrstoff im Selbststudium anzueignen."
)


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

    def test_peer_mentoring_regression(self):
        # The reported bug: earliest-match windowing put the chip on the page
        # header ("… Peer-Mentoring Psychologie hier klicken …") because
        # "Psychologie" appears there first. The densest window (Bachelorstudium
        # + Psychologie) lies in the study-start section.
        out = extract_excerpt(
            _STUDIENBEGINNER_CHUNK,
            query="Wie bewerbe ich mich für den Bachelor Psychologie?",
            max_chars=200,
        )
        assert "Peer-Mentoring" not in out
        assert "Bachelorstudium" in out

    def test_densest_window_beats_earliest_single_match(self):
        early = "Zulassung " + "filler " * 40
        cluster = "Die Zulassung zum Studium erfordert einen Antrag innerhalb der Frist."
        content = early + cluster + " tail " * 40
        out = extract_excerpt(content, query="Zulassung Antrag Frist", max_chars=120)
        assert "Antrag" in out

    def test_pronouns_do_not_drive_windowing(self):
        content = (
            "Bitte kontaktieren Sie mich frühzeitig. " + "filler " * 40 + "BACHELOR Info zum Studium." + " tail " * 40
        )
        out = extract_excerpt(content, query="Wie kann ich mich für den Bachelor anmelden?", max_chars=80)
        assert "BACHELOR" in out

    def test_claim_text_steers_excerpt(self):
        region_a = "Der Antrag auf Zulassung muss innerhalb der Frist gestellt werden."
        region_b = "Die Kosten betragen zwanzig Euro pro Semester."
        content = region_a + " filler" * 40 + " " + region_b + " tail" * 20
        query = "Antrag Zulassung Frist"
        # Without a claim, the query terms anchor the window on region A.
        without = extract_excerpt(content, query=query, max_chars=100)
        assert "Antrag" in without
        # The claim (the answer sentence citing this source) outweighs the query.
        with_claim = extract_excerpt(
            content,
            query=query,
            max_chars=100,
            claim_text="Die Gebühren betragen zwanzig Euro",
        )
        assert "Euro" in with_claim


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

    def test_answer_text_claim_anchoring_and_title_exclusion(self):
        # Title tokens ("Kontakt") must not anchor the excerpt — they cluster in
        # page headers, and the chip already sits under the titled link. The
        # claim sentence from the answer steers the window instead.
        url = "https://ssc.example/kontakt/"
        content = (
            "Kontakt Kontaktseite des SSC Psychologie. "
            + "filler " * 40
            + "Öffnungszeiten: Montag bis Freitag von 9 bis 12 Uhr geöffnet."
            + " tail" * 20
        )
        refs = self._refs(
            self._chunk(url, content=content, page_title="Kontakt", source_type="web_page", language="de")
        )
        answer = f"Das SSC ist Montag bis Freitag geöffnet ([Kontakt]({url}))."
        out = build_citations(refs, query="Wann hat das SSC geöffnet?", answer_text=answer)
        assert "Montag" in out[0]["excerpt"]
        assert "Kontaktseite" not in out[0]["excerpt"]

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
