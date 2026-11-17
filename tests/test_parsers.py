from datetime import date

import pytest

import parsers
from parsers import (
    AshbyParser, GreenhouseParser, LeverParser, NoJobDataError, StaleJobError,
    UnsupportedATSError, get_parser, html_to_markdown,
)

TODAY = date(2026, 11, 13)

ASHBY_URL = "https://jobs.ashbyhq.com/acme/3f1c2b7e-1111-2222-3333-444455556666"
GH_URL = "https://job-boards.greenhouse.io/acmecorp/jobs/4012345"
LEVER_URL = "https://jobs.lever.co/initech/0a1b2c3d-aaaa-bbbb-cccc-ddddeeeeffff"


def ld(title="Senior Backend Engineer", posted="2026-11-01", desc="<p>We use <strong>Python</strong></p>",
       org="Acme Inc"):
    return {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": title,
        "datePosted": posted,
        "description": desc,
        "hiringOrganization": {"@type": "Organization", "name": org},
    }


# ---------------------------------------------------------------- factory
@pytest.mark.parametrize("url,cls", [
    (ASHBY_URL, AshbyParser),
    (GH_URL, GreenhouseParser),
    ("https://boards.greenhouse.io/acmecorp/jobs/4012345", GreenhouseParser),
    ("https://job-boards.eu.greenhouse.io/acme/jobs/1", GreenhouseParser),
    (LEVER_URL, LeverParser),
    ("https://jobs.eu.lever.co/initech/123", LeverParser),
])
def test_factory_picks_right_parser(url, cls):
    assert isinstance(get_parser(url), cls)


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123",
    "https://evilgreenhouse.io.example.com/jobs/1",
    "https://notlever.co/acme/1",
])
def test_factory_rejects_unknown_domains(url):
    with pytest.raises(UnsupportedATSError):
        get_parser(url)


# ---------------------------------------------------------------- JSON-LD
@pytest.mark.parametrize("url,platform", [(ASHBY_URL, "ashby"), (GH_URL, "greenhouse"), (LEVER_URL, "lever")])
def test_reads_json_ld_for_each_ats(make_page, url, platform):
    job = get_parser(url, today=TODAY).parse(url, make_page(ld()))
    assert job.ats_platform == platform
    assert job.title == "Senior Backend Engineer"
    assert job.date_posted == date(2026, 11, 1)
    assert job.company == "Acme Inc"
    assert "**Python**" in job.description
    assert "<p>" not in job.description


def test_html_escaped_description_is_cleaned(make_page):
    escaped = "&lt;h2&gt;Requirements&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;5+ years Python&lt;/li&gt;&lt;li&gt;AWS&lt;/li&gt;&lt;/ul&gt;"
    job = GreenhouseParser(today=TODAY).parse(GH_URL, make_page(ld(desc=escaped)))
    assert "## Requirements" in job.description
    assert "- 5+ years Python" in job.description
    assert "&lt;" not in job.description and "<li>" not in job.description


def test_datetime_with_timezone(make_page):
    job = LeverParser(today=TODAY).parse(LEVER_URL, make_page(ld(posted="2026-11-10T14:03:00.000Z")))
    assert job.date_posted == date(2026, 11, 10)


def test_graph_and_list_payloads(make_page):
    graph = {"@context": "https://schema.org", "@graph": [{"@type": "Organization", "name": "X"}, ld()]}
    assert AshbyParser(today=TODAY).parse(ASHBY_URL, make_page(graph)).title == "Senior Backend Engineer"
    assert AshbyParser(today=TODAY).parse(ASHBY_URL, make_page([{"@type": "WebSite"}, ld()])).title


def test_raw_newlines_inside_json_string():
    # Alguns ATS emitem JSON-LD com quebras de linha cruas dentro das strings.
    html = ('<script type="application/ld+json">{"@type": "JobPosting", "title": "Dev",'
            ' "datePosted": "2026-11-05", "description": "<p>line1\nline2</p>"}</script>')
    job = LeverParser(today=TODAY).parse(LEVER_URL, html)
    assert "line1" in job.description and "line2" in job.description


def test_invalid_json_ld_is_skipped_then_fallback(make_page):
    html = ('<script type="application/ld+json">{not json</script>'
            '<div class="posting-headline"><h2>Data Engineer</h2></div>'
            '<div data-qa="job-description"><p>Spark and Airflow</p></div>')
    job = LeverParser(today=TODAY).parse(LEVER_URL, html)
    assert job.title == "Data Engineer"
    assert "Spark" in job.description
    assert job.date_posted is None
    assert job.company == "initech"  # vindo da URL


# ---------------------------------------------------------------- descarte
def test_job_older_than_30_days_is_discarded(make_page):
    with pytest.raises(StaleJobError):
        AshbyParser(today=TODAY).parse(ASHBY_URL, make_page(ld(posted="2026-10-13")))  # 31 dias


def test_job_exactly_30_days_is_kept(make_page):
    job = AshbyParser(today=TODAY).parse(ASHBY_URL, make_page(ld(posted="2026-10-14")))  # 30 dias
    assert job.date_posted == date(2026, 10, 14)


def test_custom_max_age(make_page):
    with pytest.raises(StaleJobError):
        AshbyParser(max_age_days=7, today=TODAY).parse(ASHBY_URL, make_page(ld(posted="2026-11-01")))


# ---------------------------------------------------------------- fallback / erros
def test_greenhouse_html_fallback_and_embed_company():
    html = ('<h1 class="section-header">Platform Engineer</h1>'
            '<div class="job__description"><p>Kubernetes, <em>Terraform</em></p></div>')
    url = "https://boards.greenhouse.io/embed/job_app?for=globex&token=999"
    job = GreenhouseParser(today=TODAY).parse(url, html)
    assert job.title == "Platform Engineer"
    assert "Kubernetes" in job.description
    assert job.company == "globex"


def test_no_data_raises():
    with pytest.raises(NoJobDataError):
        AshbyParser(today=TODAY).parse(ASHBY_URL, "<html><body>nada</body></html>")


def test_html_to_markdown_collapses_whitespace():
    md = html_to_markdown("<p>a</p><p></p><p></p><p>b&nbsp;c</p>")
    assert md == "a\n\nb c"


def test_is_supported():
    assert parsers.is_supported(GH_URL)
    assert not parsers.is_supported("https://example.com/job")
