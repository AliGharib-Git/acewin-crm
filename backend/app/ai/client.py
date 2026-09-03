"""
Modular AI client interface.

`AIClient` is the only contract the rest of the app depends on. The
Copilot router, the tool-calling loop, and the UI never talk to a
vendor SDK directly -- they talk to this interface:

    AIClient (interface)
        |
        v
    Provider Adapter  (OpenAIClient, AvalAIClient, GapGPTClient, GroqClient,
                        OpenRouterClient, CustomClient, GeminiClient,
                        AnthropicClient, NullAIClient, ...)
        |
        v
    Selected Provider's HTTP API
        |
        v
    LLM

Which adapter is active is decided *only* by `AI_PROVIDER` in
backend/.env (see `_PROVIDER_REGISTRY` at the bottom of this file).
Adding a new provider in the future means writing ONE new class in
this module and adding one line to `_PROVIDER_REGISTRY` -- it never
requires touching the Copilot router, the tool registry, or the
frontend, because all of them depend only on `AIClient`/`AIMessage`/
`AIResponse`/`ToolDefinition`, not on any specific vendor's shapes.

Two families of adapter live here:

1. `OpenAICompatibleClient` -- a shared base class for every provider
   that speaks the OpenAI `/chat/completions` wire format (OpenAI
   itself, OpenRouter, AvalAI, GapGPT, Groq, and any generic "custom"
   OpenAI-compatible endpoint). Each concrete adapter below is only a
   few lines: a base URL, a default model, and a human-readable label
   for error messages.

2. Fully independent adapters for providers whose request/response
   shape is *not* OpenAI-compatible: `GeminiClient` (Google's
   generateContent API) and `AnthropicClient` (Claude's Messages API).
   These translate to/from the same normalized `AIMessage`/
   `AIResponse`/`ToolDefinition` contract, so from the Copilot's point
   of view they are indistinguishable from an OpenAI-compatible one.

`NullAIClient` is used whenever `AI_PROVIDER=none` (the default). It
never calls the network -- it explains that the Copilot isn't
connected yet, so the rest of the architecture can be built, wired up,
and tested before any real provider is configured.
"""
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import httpx

from app.ai.config import AISettings, get_ai_settings

# Gateway-level errors (bad gateway / service unavailable / gateway timeout)
# are almost always transient on the provider's side, so it's worth a couple
# of quick retries before giving up and surfacing an error to the user.
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.5
_REQUEST_TIMEOUT_SECONDS = 90.0


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


@dataclass
class AIMessage:
    role: MessageRole
    content: str
    name: str | None = None  # tool name, when role == tool
    tool_call_id: str | None = None  # required by OpenAI-compatible APIs on role == tool
    tool_calls: "list[ToolCallRequest] | None" = None  # set on an assistant message that requested tools


@dataclass
class ToolDefinition:
    """Describes one backend tool the model is allowed to call.
    A plain JSON-schema `parameters` object works unchanged across every
    adapter below (OpenAI-style function-calling, Gemini's
    functionDeclarations, and Claude's input_schema all consume the same
    shape), so the tool registry never needs to know which provider is
    selected."""

    name: str
    description: str
    parameters: dict = field(default_factory=dict)


@dataclass
class ToolCallRequest:
    """A single tool invocation the model asked for."""

    tool_name: str
    arguments: dict
    call_id: str = ""


@dataclass
class AIResponse:
    """Normalized result of one call to `AIClient.complete`, regardless
    of which provider produced it."""

    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    raw_provider_payload: dict | None = None


class AIClientError(RuntimeError):
    """Raised when the configured provider can't fulfil a request
    (not configured, auth failure, rate limit, etc.)."""


class AIClient(ABC):
    """Provider-independent contract for talking to a language model."""

    def __init__(self, settings: AISettings):
        self.settings = settings

    @abstractmethod
    def complete(
        self,
        messages: list[AIMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        """Send a conversation (+ optional available tools) to the model
        and return its reply, normalized into an AIResponse."""
        raise NotImplementedError


class NullAIClient(AIClient):
    """Placeholder used while AI_PROVIDER=none (or misconfigured).

    Doesn't call any network. Exists so the rest of the Copilot
    architecture (router, tool registry, response formatting) can be
    built, wired up, and tested end-to-end before any real model is
    connected.
    """

    def complete(
        self,
        messages: list[AIMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        return AIResponse(
            content=(
                "ACEWIN Copilot is not connected to an AI provider yet. "
                "Set AI_PROVIDER, AI_API_KEY and AI_MODEL in your environment "
                "once a provider is chosen; no other code needs to change."
            ),
        )


def _post_json_with_retries(url: str, headers: dict, payload: dict, provider_label: str) -> dict:
    """Shared HTTP layer for every adapter: POSTs JSON, retries transient
    gateway errors a couple of times, and raises a normalized
    `AIClientError` on anything else. Keeping this in one place means
    every adapter gets the same retry/timeout/error behaviour for free."""
    resp: httpx.Response | None = None
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            last_exc = exc
            resp = None
        else:
            last_exc = None
            if resp.status_code not in _RETRYABLE_STATUS_CODES:
                break
        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))

    if resp is None:
        raise AIClientError(f"Could not reach {provider_label}: {last_exc}") from last_exc
    if resp.status_code >= 400:
        raise AIClientError(f"{provider_label} returned {resp.status_code}: {resp.text[:500]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise AIClientError(f"{provider_label} returned a non-JSON response: {resp.text[:500]}") from exc


# ============================================================================
# Family 1: OpenAI-compatible providers (OpenAI, OpenRouter, AvalAI, GapGPT,
# Groq, and any generic "custom" OpenAI-compatible endpoint).
# ============================================================================


class OpenAICompatibleClient(AIClient):
    """Base class for any provider that speaks the OpenAI
    `/chat/completions` wire format. A concrete subclass only needs to
    set `DEFAULT_BASE_URL`, `DEFAULT_MODEL` and `PROVIDER_LABEL` (and
    override `_headers` if the provider needs non-standard auth
    headers) -- the request/response translation and retry logic live
    here, once, for every OpenAI-compatible provider.
    """

    #: Overridden per concrete provider. `None` means AI_BASE_URL is
    #: mandatory (used by CustomClient, for a provider not listed below).
    DEFAULT_BASE_URL: str | None = None
    #: Sensible default model for this provider, used only if AI_MODEL
    #: is left blank in .env. `None` means AI_MODEL is mandatory.
    DEFAULT_MODEL: str | None = "gpt-4o-mini"
    #: Human-readable name used in error messages.
    PROVIDER_LABEL: str = "the AI provider"

    def _base_url(self) -> str:
        base_url = self.settings.ai_base_url or self.DEFAULT_BASE_URL
        if not base_url:
            raise AIClientError(
                f"AI_BASE_URL must be set in backend/.env for AI_PROVIDER={self.settings.ai_provider} "
                f"(no default endpoint for {self.PROVIDER_LABEL})."
            )
        return base_url.rstrip("/")

    def _model(self) -> str:
        model = self.settings.ai_model or self.DEFAULT_MODEL
        if not model:
            raise AIClientError(
                f"AI_MODEL must be set in backend/.env for AI_PROVIDER={self.settings.ai_provider}."
            )
        return model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _to_openai_messages(messages: list[AIMessage]) -> list[dict]:
        out = []
        for m in messages:
            entry: dict = {"role": m.role.value, "content": m.content}
            if m.role == MessageRole.tool:
                # Required by OpenAI-compatible APIs: a tool-role message must
                # reference the id of the tool call it's answering, or the
                # provider rejects the whole request.
                entry["tool_call_id"] = m.tool_call_id
                if m.name:
                    entry["name"] = m.name
            if m.role == MessageRole.assistant and m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {"name": call.tool_name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in m.tool_calls
                ]
            out.append(entry)
        return out

    @staticmethod
    def _to_openai_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ]

    def complete(
        self,
        messages: list[AIMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        if not self.settings.ai_api_key:
            raise AIClientError(f"AI_API_KEY is not set for AI_PROVIDER={self.settings.ai_provider}.")

        payload: dict = {
            "model": self._model(),
            "messages": self._to_openai_messages(messages),
            "temperature": self.settings.ai_temperature,
            "max_tokens": self.settings.ai_max_tokens,
        }
        openai_tools = self._to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
            payload["tool_choice"] = "auto"

        data = _post_json_with_retries(
            f"{self._base_url()}/chat/completions", self._headers(), payload, self.PROVIDER_LABEL
        )

        try:
            choice = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise AIClientError(f"Unexpected {self.PROVIDER_LABEL} response shape: {data}") from exc

        tool_calls = []
        for call in choice.get("tool_calls") or []:
            fn = call.get("function", {})
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCallRequest(tool_name=fn.get("name", ""), arguments=arguments, call_id=call.get("id", ""))
            )

        return AIResponse(
            content=choice.get("content") or "",
            tool_calls=tool_calls,
            raw_provider_payload=data,
        )


class OpenAIClient(OpenAICompatibleClient):
    """Official OpenAI API (https://api.openai.com)."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"
    PROVIDER_LABEL = "OpenAI"


class OpenRouterClient(OpenAICompatibleClient):
    """AIClient implementation for OpenRouter (https://openrouter.ai).

    OpenRouter exposes an OpenAI-compatible /chat/completions endpoint in
    front of many underlying models (including Gemini and Claude), so it
    doubles as a one-key way to reach almost any model without a
    dedicated adapter.
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openai/gpt-4o-mini"
    PROVIDER_LABEL = "OpenRouter"

    def _headers(self) -> dict:
        headers = super()._headers()
        headers["HTTP-Referer"] = "https://acewin.local"
        headers["X-Title"] = "ACEWIN Copilot"
        return headers


class AvalAIClient(OpenAICompatibleClient):
    """AvalAI's OpenAI-compatible endpoint, accessible from Iran
    (https://avalai.ir)."""

    DEFAULT_BASE_URL = "https://api.avalai.ir/v1"
    DEFAULT_MODEL = "gpt-4o-mini"
    PROVIDER_LABEL = "AvalAI"


class GapGPTClient(OpenAICompatibleClient):
    """GapGPT's OpenAI-compatible endpoint, accessible from Iran
    (https://gapgpt.app). Proxies OpenAI, Gemini and Claude models behind
    one key using the standard OpenAI request/response shape."""

    DEFAULT_BASE_URL = "https://api.gapgpt.app/v1"
    DEFAULT_MODEL = "gpt-4o-mini"
    PROVIDER_LABEL = "GapGPT"


class GroqClient(OpenAICompatibleClient):
    """Groq's OpenAI-compatible endpoint (https://groq.com) -- fast
    inference for open models like Llama and Mixtral."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    PROVIDER_LABEL = "Groq"


class CustomClient(OpenAICompatibleClient):
    """Escape hatch for any OpenAI-compatible endpoint not listed above
    (a self-hosted model, an internal gateway, a provider that launched
    after this file was written, ...). Requires AI_BASE_URL and AI_MODEL
    to be set explicitly in backend/.env -- there is no sensible
    default for an unknown endpoint."""

    DEFAULT_BASE_URL = None
    DEFAULT_MODEL = None
    PROVIDER_LABEL = "the custom AI provider"


# ============================================================================
# Family 2: providers with their own, non-OpenAI-compatible wire format.
# ============================================================================


class GeminiClient(AIClient):
    """Google Gemini via the Generative Language API
    (https://ai.google.dev). Uses `generateContent` with function
    calling, translated to/from the same normalized AIMessage/AIResponse
    contract every other adapter uses.
    """

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-2.5-flash"
    PROVIDER_LABEL = "Gemini"

    def _base_url(self) -> str:
        return (self.settings.ai_base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def _model(self) -> str:
        return self.settings.ai_model or self.DEFAULT_MODEL

    @staticmethod
    def _to_gemini_contents(messages: list[AIMessage]) -> tuple[dict | None, list[dict]]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for m in messages:
            if m.role == MessageRole.system:
                system_parts.append(m.content)
            elif m.role == MessageRole.user:
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == MessageRole.assistant:
                parts = []
                if m.content:
                    parts.append({"text": m.content})
                for call in m.tool_calls or []:
                    parts.append({"functionCall": {"name": call.tool_name, "args": call.arguments}})
                contents.append({"role": "model", "parts": parts})
            elif m.role == MessageRole.tool:
                try:
                    response_obj = json.loads(m.content)
                except (TypeError, json.JSONDecodeError):
                    response_obj = {"result": m.content}
                if not isinstance(response_obj, dict):
                    response_obj = {"result": response_obj}
                contents.append(
                    {"role": "user", "parts": [{"functionResponse": {"name": m.name, "response": response_obj}}]}
                )
        system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]} if system_parts else None
        return system_instruction, contents

    @staticmethod
    def _to_gemini_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "functionDeclarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {"type": "object", "properties": {}},
                    }
                    for t in tools
                ]
            }
        ]

    def complete(
        self,
        messages: list[AIMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        if not self.settings.ai_api_key:
            raise AIClientError("AI_API_KEY is not set for AI_PROVIDER=gemini.")

        system_instruction, contents = self._to_gemini_contents(messages)
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.settings.ai_temperature,
                "maxOutputTokens": self.settings.ai_max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        gemini_tools = self._to_gemini_tools(tools)
        if gemini_tools:
            payload["tools"] = gemini_tools

        url = f"{self._base_url()}/models/{self._model()}:generateContent?key={self.settings.ai_api_key}"
        data = _post_json_with_retries(url, {"Content-Type": "application/json"}, payload, self.PROVIDER_LABEL)

        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
            raise AIClientError(f"Gemini returned no answer ({reason}).")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text_chunks = [p["text"] for p in parts if "text" in p]
        tool_calls = [
            ToolCallRequest(
                tool_name=p["functionCall"].get("name", ""),
                arguments=p["functionCall"].get("args") or {},
                call_id=f"gemini-call-{i}",
            )
            for i, p in enumerate(parts)
            if "functionCall" in p
        ]

        return AIResponse(content="".join(text_chunks), tool_calls=tool_calls, raw_provider_payload=data)


class AnthropicClient(AIClient):
    """Claude via Anthropic's Messages API
    (https://api.anthropic.com/v1/messages). Selected with
    AI_PROVIDER=claude.
    """

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-sonnet-4-6"
    ANTHROPIC_VERSION = "2023-06-01"
    PROVIDER_LABEL = "Claude"

    def _base_url(self) -> str:
        return (self.settings.ai_base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def _model(self) -> str:
        return self.settings.ai_model or self.DEFAULT_MODEL

    def _headers(self) -> dict:
        return {
            "x-api-key": self.settings.ai_api_key or "",
            "anthropic-version": self.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    @staticmethod
    def _to_anthropic_messages(messages: list[AIMessage]) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        out: list[dict] = []
        for m in messages:
            if m.role == MessageRole.system:
                system_parts.append(m.content)
            elif m.role == MessageRole.user:
                out.append({"role": "user", "content": [{"type": "text", "text": m.content}]})
            elif m.role == MessageRole.assistant:
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for call in m.tool_calls or []:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call.call_id or f"call_{call.tool_name}",
                            "name": call.tool_name,
                            "input": call.arguments,
                        }
                    )
                out.append({"role": "assistant", "content": content})
            elif m.role == MessageRole.tool:
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
        return ("\n\n".join(system_parts) or None), out

    @staticmethod
    def _to_anthropic_tools(tools: list[ToolDefinition] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters or {"type": "object", "properties": {}},
            }
            for t in tools
        ]

    def complete(
        self,
        messages: list[AIMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        if not self.settings.ai_api_key:
            raise AIClientError("AI_API_KEY is not set for AI_PROVIDER=claude.")

        system_text, anthropic_messages = self._to_anthropic_messages(messages)
        payload: dict = {
            "model": self._model(),
            "max_tokens": self.settings.ai_max_tokens,
            "temperature": self.settings.ai_temperature,
            "messages": anthropic_messages,
        }
        if system_text:
            payload["system"] = system_text
        anthropic_tools = self._to_anthropic_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        data = _post_json_with_retries(
            f"{self._base_url()}/messages", self._headers(), payload, self.PROVIDER_LABEL
        )

        blocks = data.get("content") or []
        text_chunks = [b["text"] for b in blocks if b.get("type") == "text"]
        tool_calls = [
            ToolCallRequest(tool_name=b.get("name", ""), arguments=b.get("input") or {}, call_id=b.get("id", ""))
            for b in blocks
            if b.get("type") == "tool_use"
        ]

        return AIResponse(content="".join(text_chunks), tool_calls=tool_calls, raw_provider_payload=data)


# --- Provider registry -----------------------------------------------------
# Add a new provider by writing a class above (or in its own module) and
# registering it here. `get_ai_client()` is the single place that decides
# which implementation is active, so nothing else in the app -- not the
# Copilot router, not the tool registry, not the frontend -- needs to know
# providers exist at all. Selecting a provider is a one-line change to
# backend/.env: AI_PROVIDER=<key below>.
_PROVIDER_REGISTRY: dict[str, type[AIClient]] = {
    "none": NullAIClient,
    "openai": OpenAIClient,
    "openrouter": OpenRouterClient,
    "avalai": AvalAIClient,
    "gapgpt": GapGPTClient,
    "groq": GroqClient,
    "gemini": GeminiClient,
    "claude": AnthropicClient,
    "custom": CustomClient,
}


def get_ai_client() -> AIClient:
    settings = get_ai_settings()
    provider_key = settings.ai_provider.lower()
    provider_cls = _PROVIDER_REGISTRY.get(provider_key)
    if provider_cls is None:
        raise AIClientError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}'. "
            f"Available providers: {', '.join(_PROVIDER_REGISTRY)}"
        )
    if provider_cls is not NullAIClient and not settings.is_configured:
        raise AIClientError("AI_API_KEY and AI_MODEL must be set for the selected AI_PROVIDER.")
    return provider_cls(settings)
