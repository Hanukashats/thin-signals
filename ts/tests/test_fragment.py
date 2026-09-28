"""A missing snippet is not a missing paper. Recovery uses the official record, not the title."""
from ts.harness import Harness
from ts.scale import fetch_abstract
from ts.sources.connectors import Hit


class _Response:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def test_source_keeps_the_connector_doi():
    hit = Hit("europepmc", "https://europepmc.org/article/MED/1", "Sensor", "", "paper", doi="10.1/a")
    assert Harness()._sources([hit])[0]["doi"] == "10.1/a"


def test_europepmc_article_without_snippet_recovers_the_abstract(monkeypatch):
    def fake(url, params=None, **kwargs):
        assert "europepmc" in url
        assert params["resultType"] == "core"
        assert "EXT_ID:9" in params["query"]
        return _Response(200, {"resultList": {"result": [{"abstractText": "The electrolyzer splits water."}]}})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://europepmc.org/article/MED/9", "snippet": ""}]}
    assert "electrolyzer" in fetch_abstract(card)


def test_cordis_project_uses_the_objective(monkeypatch):
    def fake(url, **kwargs):
        assert "/project/id/101" in url
        return _Response(200, {"teaser": "short", "objective": "The grant builds a pilot line."})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://cordis.europa.eu/project/id/101", "snippet": ""}]}
    assert fetch_abstract(card).startswith("The grant")


def test_nature_article_id_is_asked_as_its_doi(monkeypatch):
    seen = []

    def fake(url, **kwargs):
        seen.append(url)
        return _Response(200, {})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://www.nature.com/articles/s41928-022-00899-4", "snippet": ""}]}
    assert fetch_abstract(card) == ""
    assert seen and "10.1038/s41928-022-00899-4" in seen[0]


def test_arxiv_abs_without_snippet_recovers_the_summary(monkeypatch):
    atom = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><summary>A laser terminal for satellites.</summary></entry></feed>"""

    class Response:
        status_code = 200
        text = atom

        def json(self):
            return {}

    def fake(url, params=None, **kwargs):
        assert "arxiv.org" in url
        assert params["id_list"] == "2111.08454v1"
        return Response()

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://arxiv.org/abs/2111.08454v1", "snippet": ""}]}
    assert "laser terminal" in fetch_abstract(card)


def test_repository_without_text_is_not_a_fragment(monkeypatch):
    def fake(*args, **kwargs):
        raise AssertionError("no network")

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://github.com/josh/study", "connector": "github", "snippet": ""}]}
    assert fetch_abstract(card) == ""


def test_supplement_file_uses_the_paper_itself(monkeypatch):
    seen = []

    def fake(url, **kwargs):
        seen.append(url)
        return _Response(200, {"abstract_inverted_index": {"motor": [0], "runs": [1]}})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://doi.org/10.1109/tec.2026.3669789/mm3", "snippet": ""}]}
    assert "motor" in fetch_abstract(card)
    assert seen and "/mm3" not in seen[0]


def test_crossref_abstract_is_used_when_openalex_has_none(monkeypatch):
    def fake(url, **kwargs):
        if "openalex" in url:
            return _Response(200, {})
        if "crossref" in url:
            return _Response(200, {"message": {"abstract": "<jats:p>The inverter cools the module.</jats:p>"}})
        return _Response(404, {})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://doi.org/10.4271/2021-01-0218", "snippet": ""}]}
    assert "inverter cools" in fetch_abstract(card)


def test_closed_publisher_record_stays_empty(monkeypatch):
    def fake(url, **kwargs):
        return _Response(200, {"abstract_inverted_index": None})

    monkeypatch.setattr("ts.scale.httpx.get", fake)
    card = {"sources": [{"url": "https://doi.org/10.1000/closed", "connector": "crossref", "snippet": ""}]}
    assert fetch_abstract(card) == ""
