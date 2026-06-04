"""Anthropic Claude SDK の async ラッパー。テスト時はSDKをモック注入する。"""

from typing import Protocol, TypedDict

from anthropic import AsyncAnthropic

from app.config import settings


class _SDKLike(Protocol):
    messages: object


class Attachment(TypedDict):
    """One image or PDF attachment, base64-encoded."""

    media_type: str  # e.g. "image/png", "application/pdf"
    data: str  # base64-encoded payload


class ClaudeClient:
    def __init__(self, sdk: _SDKLike, model: str) -> None:
        self._sdk = sdk
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        response = await self._sdk.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=history,
        )
        return response.content[0].text

    async def complete_multimodal(
        self,
        *,
        system_prompt: str,
        text: str,
        attachments: list[Attachment],
        max_tokens: int = 1024,
    ) -> str:
        content: list[dict] = [{"type": "text", "text": text}]
        for att in attachments:
            media = att["media_type"]
            if media.startswith("image/"):
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media,
                            "data": att["data"],
                        },
                    }
                )
            elif media == "application/pdf":
                content.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media,
                            "data": att["data"],
                        },
                    }
                )
            # text-only attachments are inlined into the user text upstream;
            # unknown media types are dropped silently.

        response = await self._sdk.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text


def get_claude_client() -> ClaudeClient:
    """FastAPI Dependsから利用するファクトリ。"""
    sdk = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return ClaudeClient(sdk=sdk, model=settings.anthropic_model)
