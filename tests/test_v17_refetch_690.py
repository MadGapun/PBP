"""Regression #690: stellenbeschreibung_nachladen / fetch_description_from_detail
kappte Stellenbeschreibungen hart bei 2000 Zeichen. max_chars ist jetzt
parametrierbar; das explizite Nachladen einer einzelnen Stelle nutzt 20000,
Bulk-Scraper behalten den 2000er-Default.
"""

JSONLD = (
    '<html><head><script type="application/ld+json">'
    '{{"@type": "JobPosting", "description": "{desc}"}}'
    '</script></head><body>x</body></html>'
)


def test_690_jsonld_respects_max_chars():
    from bewerbungs_assistent.job_scraper import extract_jobposting_jsonld
    html = JSONLD.format(desc="A" * 8000)
    assert len(extract_jobposting_jsonld(html, max_chars=2000)["description"]) == 2000
    assert len(extract_jobposting_jsonld(html, max_chars=20000)["description"]) == 8000


class _FakeResp:
    status_code = 200

    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self, text):
        self._text = text

    def get(self, url, timeout=None):
        return _FakeResp(self._text)


def test_690_fetch_description_honors_max_chars():
    from bewerbungs_assistent.job_scraper import fetch_description_from_detail
    html = JSONLD.format(desc="B" * 8000)
    client = _FakeClient(html)
    # v1.7.23 (#952): Der 2000er-Default WAR die Ursache. Er kappte
    # ausgerechnet im Refetch, der duenne Beschreibungen heilen soll —
    # die Kette aus #622/#756 holte damit zuverlaessig immer wieder
    # denselben halben Text. Jetzt greift die Notbremse aus
    # `textgrenzen`, und der volle Text kommt an.
    assert len(fetch_description_from_detail("http://x", client)) == 8000
    # Eine ausdrueckliche Grenze wird weiterhin respektiert.
    assert len(fetch_description_from_detail("http://x", client, max_chars=500)) == 500
