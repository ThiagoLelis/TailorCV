# Job Hunter & AI Resume Generator

Pipeline: **Google Alerts (RSS)** → valida se a vaga está aberta → extrai JSON-LD `JobPosting` (Ashby / Greenhouse / Lever) → salva no SQLite → gera um currículo Markdown sob medida com LLM.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # preencha ANTHROPIC_API_KEY
# edite base_resume.md com o seu currículo
# edite feeds.txt com as URLs RSS dos seus Google Alerts
```

No Google Alerts, em "Mostrar opções" escolha **Enviar para: Feed RSS** e copie a URL do ícone RSS.
Dica de busca: `site:jobs.ashbyhq.com OR site:job-boards.greenhouse.io OR site:jobs.lever.co "python" "backend"`.

## Uso

```bash
python main.py                         # processa todos os feeds de feeds.txt
python main.py --dry-run               # valida/parseia/salva sem chamar a LLM
python main.py --url https://jobs.lever.co/empresa/uuid   # uma vaga específica
python main.py --max-age-days 14 -v
pytest -q                              # testes (todos mockados, sem rede)
```

Saída: `generated_cvs/{AAAA-MM-DD}_{empresa}_{cargo}.md` e a tabela `jobs` em `jobs.db`
(status: `pending` → `cv_generated` ou `failed`). Vagas já com `cv_generated` são puladas nas próximas execuções.

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `ingestor.py` | Lê feeds, desembrulha `google.com/url?url=...`, deduplica |
| `validator.py` | `GET` com `allow_redirects=False`; só `200` = aberta. Devolve o HTML para o parser |
| `parsers.py` | `ATSParser` abstrato (template method: JSON-LD → fallback HTML), 3 estratégias e `get_parser(url)` |
| `cv_generator.py` | Prompt da spec (regras no system, currículo + vaga no user). Anthropic ou OpenAI via `LLM_PROVIDER` |
| `storage.py` | SQLite; `id` = hash da URL |
| `main.py` | Orquestração + CLI |

Para adicionar um ATS (ex.: Workable): crie uma subclasse de `ATSParser` com `platform`, `domains` e `fallback_extract`, e inclua-a em `PARSERS`.

## Decisões em relação à spec

- **Modelo:** `claude-3-5-sonnet-latest` foi aposentado; o padrão é `claude-sonnet-5-5`, configurável por `LLM_MODEL`.
- **Validação:** além de 301/302/404, qualquer status ≠ 200 (403, 5xx, erro de rede) também é tratado como indisponível.
- **Descarte por data:** vagas com mais de 30 dias são descartadas; vagas **sem** `datePosted` são mantidas.
- **Data no nome do arquivo:** data de geração do CV.
