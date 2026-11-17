"""Geração do currículo otimizado via LLM."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from models import JobPosting

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = """Você é um Tech Recruiter Senior e Especialista em Otimização de Currículos para ATS (Applicant Tracking Systems).

O candidato possui um currículo base focado em Engenharia de Software (Python, Cloud, AI, Backend). O objetivo é adaptar este currículo base para que ele dê "match" perfeito com a descrição da vaga fornecida, mantendo a VERDADE ABSOLUTA sobre a experiência do candidato, mas alterando o destaque, a ordem dos bullet points e as palavras-chave para refletir o que a vaga pede.

<regras_de_otimizacao>
1. NÃO invente experiências, cargos ou tecnologias que não estão no currículo base.
2. Analise a <descricao_da_vaga> e identifique as 5 palavras-chave técnicas e de soft skills mais importantes.
3. Reescreva o "Summary/Profile" para alinhar imediatamente com as dores que a vaga quer resolver.
4. Nos "Work Experiences", puxe para cima (primeiros bullet points) as conquistas e métricas do currículo base que mais se relacionam com a stack ou contexto da vaga.
5. Remova jargões genéricos e substitua pela terminologia exata usada na descrição da vaga.
6. O formato de saída DEVE ser estritamente em Markdown.
</regras_de_otimizacao>"""


def build_user_prompt(base_resume: str, job_title: str, job_description: str) -> str:
    # Concatenação simples (sem str.format) para não quebrar com chaves no conteúdo.
    return (
        "<curriculo_base>\n" + base_resume.strip() + "\n</curriculo_base>\n\n"
        "<descricao_da_vaga>\n" + job_title.strip() + "\n" + job_description.strip() + "\n</descricao_da_vaga>\n\n"
        "Gere o currículo otimizado em formato Markdown estruturado. "
        "Não inclua texto introdutório, apenas o Markdown final."
    )


def _strip_fences(text: str) -> str:
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*?)\n```\s*", text, flags=re.S)
    return (m.group(1) if m else text).strip() + "\n"


class CVGenerator:
    def __init__(self, base_resume_path: str | Path = "base_resume.md", client=None,
                 provider: str | None = None, model: str | None = None, max_tokens: int | None = None):
        self.base_resume = Path(base_resume_path).read_text(encoding="utf-8")
        self.provider = (provider or os.getenv("LLM_PROVIDER", "anthropic")).lower()
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self.client = client or self._make_client()

    def _make_client(self):
        if self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
        if self.provider == "openai":
            import openai
            return openai.OpenAI()  # lê OPENAI_API_KEY do ambiente
        raise ValueError(f"LLM_PROVIDER desconhecido: {self.provider}")

    def generate(self, job: JobPosting) -> str:
        user_prompt = build_user_prompt(self.base_resume, job.title, job.description)
        log.info("Gerando CV para '%s' (%s) com %s", job.title, job.company, self.model)

        if self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        else:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = resp.choices[0].message.content or ""

        if not text.strip():
            raise RuntimeError("A LLM retornou uma resposta vazia")
        return _strip_fences(text)
