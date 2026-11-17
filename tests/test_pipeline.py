import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import main
from cv_generator import SYSTEM_PROMPT, CVGenerator, build_user_prompt
from models import JobPosting
from storage import JobStore

RECENT = date.today().isoformat()


def page(title, posted=RECENT, org="Acme"):
    payload = {"@type": "JobPosting", "title": title, "datePosted": posted,
               "description": "<p>Python, AWS, LLMs</p>", "hiringOrganization": {"name": org}}
    return f'<script type="application/ld+json">{json.dumps(payload)}</script>'


def fake_anthropic(text="# Fulano\n\n## Summary\nBackend Python"):
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])
    return client


# ---------------------------------------------------------------- cv_generator
def test_prompt_contains_resume_and_job_and_survives_braces():
    p = build_user_prompt("Resume {com chaves}", "Backend Dev", "Usa {Python}")
    assert "<curriculo_base>\nResume {com chaves}\n</curriculo_base>" in p
    assert "<descricao_da_vaga>\nBackend Dev\nUsa {Python}\n</descricao_da_vaga>" in p


def test_generator_calls_anthropic_and_strips_fences(tmp_path):
    resume = tmp_path / "base_resume.md"
    resume.write_text("# Fulano")
    client = fake_anthropic("```markdown\n# Fulano Otimizado\n```")
    gen = CVGenerator(resume, client=client, provider="anthropic", model="test-model")
    out = gen.generate(JobPosting(url="u", ats_platform="lever", title="Dev", description="Python"))
    assert out == "# Fulano Otimizado\n"
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "test-model" and kwargs["system"] == SYSTEM_PROMPT
    assert "# Fulano" in kwargs["messages"][0]["content"]


# ---------------------------------------------------------------- pipeline
def test_end_to_end_pipeline(tmp_path):
    urls = {
        "https://jobs.lever.co/acme/1": (200, page("Senior Python Engineer")),
        "https://jobs.ashbyhq.com/acme/2": (302, ""),                               # fechada
        "https://job-boards.greenhouse.io/acme/jobs/3": (200, page("Old", "2020-01-01")),  # antiga
        "https://www.linkedin.com/jobs/view/4": (200, ""),                          # não suportada
    }
    session = MagicMock()
    session.get.side_effect = lambda url, **kw: SimpleNamespace(status_code=urls[url][0], text=urls[url][1])

    resume = tmp_path / "base_resume.md"
    resume.write_text("# Fulano")
    gen = CVGenerator(resume, client=fake_anthropic(), provider="anthropic", model="m")
    store = JobStore(tmp_path / "jobs.db")
    out = tmp_path / "generated_cvs"

    stats = main.run(list(urls), store, gen, out, session=session)

    assert (stats.generated, stats.closed, stats.stale, stats.unsupported) == (1, 1, 1, 1)
    f = out / f"{date.today().isoformat()}_acme_senior-python-engineer.md"
    assert f.exists() and "Backend Python" in f.read_text()
    rows = store.all()
    assert len(rows) == 1 and rows[0]["status"] == "cv_generated" and rows[0]["cv_path"] == str(f)

    # 2ª execução: vaga já processada é pulada sem nova chamada HTTP/LLM
    session.get.reset_mock()
    stats2 = main.run(["https://jobs.lever.co/acme/1"], store, gen, out, session=session)
    assert stats2.already_done == 1 and not session.get.called


def test_llm_failure_marks_job_failed(tmp_path):
    session = MagicMock()
    session.get.return_value = SimpleNamespace(status_code=200, text=page("Dev"))
    resume = tmp_path / "r.md"
    resume.write_text("x")
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("rate limit")
    store = JobStore(tmp_path / "db.sqlite")
    stats = main.run(["https://jobs.lever.co/acme/9"], store,
                     CVGenerator(resume, client=client, provider="anthropic"), tmp_path / "out", session=session)
    assert stats.failed == 1
    row = store.all()[0]
    assert row["status"] == "failed" and "rate limit" in row["error"]


def test_slugify_and_filename():
    job = JobPosting(url="u", ats_platform="x", title="Engenheiro(a) de Software Sênior / IA", company="Ação S.A.")
    assert main.cv_filename(job, date(2026, 1, 2)) == "2026-01-02_acao-s-a_engenheiro-a-de-software-senior-ia.md"
