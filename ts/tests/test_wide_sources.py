"""Parsers for the wider primary scan. Fixtures only, no network."""
from ts.sources.connectors import (
    ClinicalTrialsConnector,
    CordisConnector,
    DoajConnector,
    EuropePmcConnector,
    HalConnector,
    IetfConnector,
    NihConnector,
    NsfConnector,
    OpenReviewConnector,
    SecConnector,
)
from ts.sources.trust import classify


def test_new_primary_hosts_are_primary():
    assert classify("https://europepmc.org/article/MED/1", "paper") == "primary"
    assert classify("https://doi.org/10.1000/x", "paper") == "primary"
    assert classify("https://www.nsf.gov/awardsearch/showAward?AWD_ID=1", "registry") == "primary"
    assert classify("https://reporter.nih.gov/project-details/1", "registry") == "primary"
    assert classify("https://cordis.europa.eu/project/id/1", "registry") == "primary"
    assert classify("https://datatracker.ietf.org/doc/draft-a/", "registry") == "primary"
    assert classify("https://www.sec.gov/Archives/edgar/data/1/a/b.htm", "registry") == "primary"


def test_europepmc_keeps_doi_and_date():
    seen = []

    def get(url):
        seen.append(url)
        return '{"resultList":{"result":[{"id":"1","source":"MED","title":"Sensor","abstractText":"The cell splits water.","doi":"10.1/a","firstPublicationDate":"2024-05-01"}]}}'

    hit = EuropePmcConnector(get).search("q")[0]
    assert "resultType=core" in seen[0]
    assert "splits water" in hit.snippet
    assert hit.url == "https://europepmc.org/article/MED/1" and hit.doi == "10.1/a" and hit.published == "2024-05-01"


def test_grant_and_standard_links():
    nsf = '{"response":{"award":[{"id":"12","title":"Cell","abstractText":"lab","date":"08/04/2026"}]}}'
    assert NsfConnector(lambda url: nsf).search("q")[0].published == "2026-08-04"
    nih = '{"results":[{"appl_id":9,"project_title":"Cell","abstract_text":"lab","project_start_date":"2022-08-01T00:00:00"}]}'
    assert NihConnector(lambda url, payload: nih).search("q")[0].url.endswith("/9")
    cordis = '{"hits":{"hit":{"project":{"id":"797546","acronym":"FASTEST","teaser":"cells","startDate":"2018-06-01"}}}}'
    hit = CordisConnector(lambda url: cordis).search("q")[0]
    assert hit.url.endswith("/797546") and hit.published == "2018-06-01"
    ietf = '{"objects":[{"name":"draft-a","title":"QUIC","abstract":"transport","time":"2015-03-24T23:03:38Z"}]}'
    assert IetfConnector(lambda url: ietf).search("q")[0].url.endswith("/draft-a/")


def test_papers_trials_and_filings():
    doaj = '{"results":[{"bibjson":{"title":"Film","year":"2021","abstract":"nano","identifier":[{"type":"doi","id":"10.1/b"}]}}]}'
    assert DoajConnector(lambda url: doaj).search("q")[0].doi == "10.1/b"
    hal = '{"response":{"docs":[{"title_s":["Lens"],"uri_s":"https://hal.science/hal-1","producedDate_tdate":"2010-05-25T00:00:00Z","abstract_s":["text"]}]}}'
    assert HalConnector(lambda url: hal).search("q")[0].title == "Lens"
    review = '{"notes":[{"id":"abc","content":{"title":{"value":"Net"}},"cdate":1600000000000}]}'
    assert OpenReviewConnector(lambda url: review).search("q")[0].title == "Net"
    trial = '{"studies":[{"protocolSection":{"identificationModule":{"nctId":"NCT1","briefTitle":"Study"},"statusModule":{"startDateStruct":{"date":"2023-02-20"}}}}]}'
    assert ClinicalTrialsConnector(lambda url: trial).search("q")[0].published == "2023-02-20"
    sec = '{"hits":{"hits":[{"_id":"0001-14-000192:report.htm","_source":{"ciks":["0000949428"],"adsh":"0001513162-14-000192","form":"10-K","file_date":"2014-03-31","display_names":["ACME"],"file_description":"annual"}}]}}'
    hit = SecConnector(lambda url: sec).search("q")[0]
    assert hit.url.startswith("https://www.sec.gov/Archives/edgar/data/949428/") and hit.published == "2014-03-31"
