# TailorCV

Gera currículos sob medida para cada vaga e acompanha cada candidatura num board Kanban local.
Sem banco de dados e sem nuvem: os arquivos em `generated_cvs/` são a única fonte da verdade.

## Fluxo

1. No Claude Code, rode `/tailor-cv` com o link de uma vaga. A skill gera o **Pacote** (CV `.md`/`.pdf`,
   `vaga_info.md` com pesquisa e preparação) e a **Candidatura** (`application.md`) em `generated_cvs/awaiting/`.
2. Abra o board e mova a **Candidatura** entre as etapas conforme o processo avança.

## Board

```bash
python3 board.py              # http://127.0.0.1:8765
python3 board.py --port 9000  # outra porta
```

Só Python 3.10+ da biblioteca padrão, sem `pip install`. Escuta apenas em `127.0.0.1`.

- **Etapas** (cada uma é uma pasta): `awaiting/` → `applied/` → `in-process/` → `offer/` → `closed/`.
  Mover uma Candidatura move a pasta dela. Ao encerrar, o board pede o motivo (rejeitado, desisti, vaga fechada).
- **Candidatura aberta:** links da vaga, PDFs do CV e da carta, `vaga_info.md` renderizado e as suas anotações
  (corpo do `application.md`, edição livre em Markdown; `Ctrl+S` salva).
- A interface fica em português se o navegador estiver em português; caso contrário, em inglês.
- Depois de rodar a skill, clique em **Atualizar** (ou recarregue a página) para ver a Candidatura nova.

```text
generated_cvs/applied/2026-11-16_Superhuman_AI-Engineer-Mail/
├── Thiago Lelis - Superhuman.md / .pdf
├── vaga_info.md        # gerado pela skill (pode ser regenerado)
└── application.md      # frontmatter (company, role, job_url, apply_url, created, closed_reason) + suas anotações
```

Vocabulário em [GLOSSARY.md](GLOSSARY.md); decisões em [docs/adr/](docs/adr/).

## Testes

```bash
python3 -m unittest discover -s tests   # ou: pytest -q
```
