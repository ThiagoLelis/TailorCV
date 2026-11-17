from unittest.mock import MagicMock

import pytest
import requests

import ingestor
import validator

GA_LINK = ("https://www.google.com/url?rct=j&sa=t&url=https://jobs.lever.co/initech/abc-123"
           "&ct=ga&cd=CAEYACoTNjM&usg=AOvVaw0")

ATOM_FEED = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Google Alert - python engineer</title>
  <entry>
    <id>tag:google.com,2013:googlealerts/feed:1</id>
    <title type="html">Senior &lt;b&gt;Python&lt;/b&gt; Engineer - Initech</title>
    <link href="{GA_LINK.replace('&', '&amp;')}"/>
  </entry>
  <entry>
    <id>tag:google.com,2013:googlealerts/feed:2</id>
    <title type="html">Dup</title>
    <link href="{GA_LINK.replace('&', '&amp;')}"/>
  </entry>
</feed>"""


def test_extract_target_url_unwraps_google_redirect():
    assert ingestor.extract_target_url(GA_LINK) == "https://jobs.lever.co/initech/abc-123"


def test_extract_target_url_keeps_plain_links():
    url = "https://jobs.ashbyhq.com/acme/1"
    assert ingestor.extract_target_url(url) == url


def test_extract_target_url_decodes_percent_encoding():
    link = "https://www.google.com/url?url=https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F1%3Fgh_src%3Dx"
    assert ingestor.extract_target_url(link) == "https://boards.greenhouse.io/acme/jobs/1?gh_src=x"


def test_fetch_feed_items_parses_atom_and_dedups():
    items = ingestor.collect_items([ATOM_FEED])
    assert len(items) == 1
    assert items[0].url == "https://jobs.lever.co/initech/abc-123"
    assert items[0].title == "Senior Python Engineer - Initech"


def test_load_feed_urls(tmp_path):
    f = tmp_path / "feeds.txt"
    f.write_text("# comentário\n\nhttps://www.google.com/alerts/feeds/1/2\n  https://x/feed  \n")
    assert ingestor.load_feed_urls(f) == ["https://www.google.com/alerts/feeds/1/2", "https://x/feed"]


# ---------------------------------------------------------------- validator
def _session(status, text="<html></html>"):
    s = MagicMock()
    s.get.return_value = MagicMock(status_code=status, text=text)
    return s


def test_200_is_open_and_returns_html():
    s = _session(200, "<html>ok</html>")
    r = validator.validate("https://jobs.lever.co/a/1", session=s)
    assert r.is_open and r.html == "<html>ok</html>"
    assert s.get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("status", [301, 302, 404, 500, 403])
def test_non_200_is_closed(status):
    assert validator.is_job_open("https://jobs.lever.co/a/1", session=_session(status)) is False


def test_network_error_is_closed():
    s = MagicMock()
    s.get.side_effect = requests.ConnectionError("boom")
    r = validator.validate("https://jobs.lever.co/a/1", session=s)
    assert not r.is_open and r.status_code is None
