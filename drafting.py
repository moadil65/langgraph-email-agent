"""Generate and revise email text with a local Ollama-hosted Llama model.

The LLM is allowed to suggest subject/body only; the graph owns recipient and
Gmail sending. The intentionally simplistic --mock mode is for plumbing tests.
"""

import json
import os
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen


def check_ollama(base_url: str, model: str) -> None:
    """Give useful setup errors before starting a drafting workflow."""
    url = base_url.rstrip('/') + '/api/tags'
    try:
        with urlopen(url, timeout=5) as response:
            models = json.load(response).get('models', [])
    except (OSError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(
            f'Cannot reach Ollama at {base_url}. Install and open Ollama '
            '(https://ollama.com/download), or run `ollama serve`, then retry.'
        ) from exc
    available = [item.get('name', '') for item in models]
    model_available = any(
        name == model or (':' not in model and name.startswith(model + ':'))
        for name in available
    )
    if not model_available:
        raise RuntimeError(
            f'Ollama is running, but model {model!r} is not installed. '
            f'Run `ollama pull {model}` then retry. '
            f'Available models: {", ".join(available) or "none"}.'
        )


class DraftWriter:
    def __init__(self, mock: bool = False):
        self.mock = mock
        self.structured_llm = None
        if not mock:
            from langchain_ollama import ChatOllama
            from pydantic import BaseModel, Field

            model = os.getenv('OLLAMA_MODEL', 'llama3.2')
            base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            check_ollama(base_url, model)

            class EmailFields(BaseModel):
                subject: str = Field(description='Concise email subject, single line')
                body: str = Field(description='Complete natural email body in plain text')

            # JSON schema output uses Ollama's structured-output support.
            self.structured_llm = ChatOllama(
                model=model,
                base_url=base_url,
                temperature=0.3,
            ).with_structured_output(EmailFields, method='json_schema')

    def write(self, recipient: str, instructions: str,
              current_subject: Optional[str] = None,
              current_body: Optional[str] = None,
              feedback: Optional[str] = None) -> dict:
        if self.mock:
            if feedback:
                return {
                    'subject': current_subject or 'Message',
                    'body': (current_body or '') + '\n\n[MOCK REVISION REQUEST: ' + feedback + ']',
                }
            return {
                'subject': 'Regarding your request',
                'body': 'Hello,\n\n' + instructions.strip() + '\n\nBest regards',
            }

        from langchain_core.messages import HumanMessage, SystemMessage
        if feedback:
            request = (
                f'You are rewriting an email to {recipient}.\n'
                f'Original requirements: {instructions}\n'
                f'Current subject: {current_subject}\n'
                f'Current body:\n{current_body}\n'
                f'User feedback to incorporate: {feedback}\n'
                'Write the COMPLETE new subject and body, not a list of changes. '
                'Preserve accurate details and follow the latest feedback.'
            )
        else:
            request = (
                f'Write an email addressed to {recipient}.\n'
                f'User requirements: {instructions}\n'
                'Compose a complete, ready-to-send email with a natural subject. '
                'Do not copy the user instructions verbatim.'
            )
        try:
            result = self.structured_llm.invoke([
                SystemMessage(content=(
                    'You are an excellent email ghostwriter. Write a complete, natural, '
                    'human-sounding email reflecting the user\'s intent and tone. '
                    'For a friendly note, use a warm conversational style; for business, '
                    'be professional. Follow requests for brevity. '
                    'Do not invent personal names, dates, promises, or other facts. '
                    'Avoid repeating the instruction text verbatim. '
                    'Return only the subject and body fields in the required structure. '
                    'Do not include To/Subject headers inside body. '
                    'Do not request or perform any external action; you do not control sending.'
                )),
                HumanMessage(content=request),
            ])
        except Exception as exc:
            raise RuntimeError(
                'Local Llama drafting failed. Make sure Ollama is running and '
                f'`ollama run {os.getenv("OLLAMA_MODEL", "llama3.2")}` works. '
                f'Details: {exc}'
            ) from exc
        if not result or not result.subject.strip() or not result.body.strip():
            raise RuntimeError('Llama returned an empty subject or body. Please retry.')
        return {'subject': result.subject.strip(), 'body': result.body.strip()}
