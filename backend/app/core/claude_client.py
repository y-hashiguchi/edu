"""Anthropic Claude SDK の薄いラッパー。テスト時はSDKをモック注入する。"""

from typing import Protocol

from anthropic import Anthropic

from app.config import settings


class _SDKLike(Protocol):
    messages: object


class ClaudeClient:
    def __init__(self, sdk: _SDKLike, model: str) -> None:
        self._sdk = sdk
        self._model = model

    def complete(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        response = self._sdk.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=history,
        )
        return response.content[0].text


def get_claude_client() -> ClaudeClient:
    """FastAPI Dependsから利用するファクトリ。"""
    sdk = Anthropic(api_key=settings.anthropic_api_key)
    return ClaudeClient(sdk=sdk, model=settings.anthropic_model)
