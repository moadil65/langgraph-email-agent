
import json
import os
from typing import Optional
from urllib.request import urlopen


SYSTEM_PROMPT = (
    "You are an email-writing assistant. "
    "Write natural, clear, and complete emails based on the user's requirements. "
    "Use a friendly tone for personal emails and a professional tone for business emails. "
    "Keep emails concise when requested. "
    "Do not invent names, dates, or personal details. "
    "Return only the subject and body. "
    "Do not send emails."
)


def check_ollama(base_url: str, model: str) -> None:
    url = base_url.rstrip("/") + "/api/tags"

    try:
        with urlopen(url, timeout=5) as response:
            models = json.load(response).get("models", [])
    except (OSError, TimeoutError, ValueError) as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        ) from exc

    available = [item.get("name", "") for item in models]

    installed = any(
        name == model or (
            ":" not in model and name.startswith(model + ":")
        )
        for name in available
    )

    if not installed:
        raise RuntimeError(
            f"Model {model} is not installed. Run: ollama pull {model}"
        )


class DraftWriter:

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.structured_llm = None

        if mock:
            return

        from langchain_ollama import ChatOllama
        from pydantic import BaseModel, Field

        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )

        check_ollama(base_url, model)

        class EmailFields(BaseModel):
            subject: str = Field(description="Email subject")
            body: str = Field(description="Complete email body")

        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.3
        )

        self.structured_llm = llm.with_structured_output(
            EmailFields,
            method="json_schema"
        )

    def write(
        self,
        recipient: str,
        instructions: str,
        current_subject: Optional[str] = None,
        current_body: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> dict:

        if self.mock:
            if feedback:
                return {
                    "subject": current_subject or "Message",
                    "body": (current_body or "") +
                            "\n\n[MOCK REVISION REQUEST: " + feedback + "]"
                }

            return {
                "subject": "Regarding your request",
                "body": "Hello,\n\n" + instructions.strip() +
                        "\n\nBest regards"
            }

        from langchain_core.messages import HumanMessage, SystemMessage

        if feedback:
            prompt = (
                f"Recipient: {recipient}\n"
                f"Original requirements: {instructions}\n"
                f"Current subject: {current_subject}\n"
                f"Current email: {current_body}\n"
                f"Requested changes: {feedback}\n\n"
                "Rewrite the complete email using these changes. "
                "Preserve the original requirements unless changed by the user."
            )
        else:
            prompt = (
                f"Write an email to {recipient}.\n"
                f"Requirements: {instructions}\n"
                "Generate a complete email with a subject and body. "
                "Do not copy the instructions directly."
            )

        try:
            result = self.structured_llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
        except Exception as exc:
            raise RuntimeError(
                f"Llama email generation failed: {exc}"
            ) from exc

        if not result or not result.subject.strip() or not result.body.strip():
            raise RuntimeError("Llama returned an empty email.")

        return {
            "subject": result.subject.strip(),
            "body": result.body.strip()
        }
