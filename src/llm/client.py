"""
src/llm/client.py - Wrapper goi Gemini, OpenAI, hoac Hugging Face Inference Providers
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
)
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_HUGGINGFACE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct:fastest"
HUGGINGFACE_BASE_URL = "https://router.huggingface.co/v1"


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def _normalize_gemini_model_name(model_name: str) -> str:
    cleaned = model_name.strip()
    if not cleaned:
        return DEFAULT_GEMINI_MODEL
    if cleaned.startswith("models/"):
        return cleaned.split("/", 1)[1]
    return cleaned


def _candidate_gemini_models(configured_model: str) -> list[str]:
    candidates: list[str] = []
    for model in (configured_model, *GEMINI_FALLBACK_MODELS):
        normalized = _normalize_gemini_model_name(model)
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates


def validate_llm_config() -> str:
    provider = _get_env("LLM_PROVIDER", "huggingface").lower()
    gemini_key = _get_env("GEMINI_API_KEY")
    openai_key = _get_env("OPENAI_API_KEY")
    huggingface_key = _get_env("HF_TOKEN") or _get_env("HUGGINGFACE_API_KEY")
    groq_key = _get_env("GROQ_API_KEY")

    if provider not in {"gemini", "openai", "huggingface", "groq"}:
        raise LLMConfigurationError(
            "LLM_PROVIDER khong hop le: "
            f"'{provider}'. Dung 'gemini', 'openai', 'groq' hoac 'huggingface'."
        )

    if provider == "gemini" and not gemini_key:
        raise LLMConfigurationError("Thieu GEMINI_API_KEY trong .env.")

    if provider == "openai" and not openai_key:
        raise LLMConfigurationError("Thieu OPENAI_API_KEY trong .env.")

    if provider == "groq" and not groq_key:
        raise LLMConfigurationError("Thieu GROQ_API_KEY trong .env.")

    if provider == "huggingface" and not huggingface_key:
        raise LLMConfigurationError("Thieu HF_TOKEN hoac HUGGINGFACE_API_KEY trong .env.")

    return provider


def _call_gemini(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    import google.generativeai as genai
    from google.api_core.exceptions import NotFound

    genai.configure(api_key=_get_env("GEMINI_API_KEY"))
    configured_model = _get_env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    errors: list[str] = []

    for model_name in _candidate_gemini_models(configured_model):
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            response = model.generate_content(user_prompt)
            text = getattr(response, "text", None)
            if text and text.strip():
                return text.strip()

            errors.append(f"{model_name}: response rong")
        except NotFound as e:
            logger.warning("Gemini model unavailable: %s", model_name)
            errors.append(f"{model_name}: {e}")
            continue
        except Exception as e:
            errors.append(f"{model_name}: {e}")
            raise

    raise LLMResponseError(
        "Khong co Gemini model nao kha dung. Da thu: "
        + "; ".join(errors)
    )



def _call_groq(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    from groq import Groq

    client = Groq(api_key=_get_env("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model=_get_env("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content
    if content and content.strip():
        return content.strip()
    raise LLMResponseError("Groq khong tra ve noi dung van ban.")


def _call_openai(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    from openai import OpenAI

    base_url = _get_env("OPENAI_BASE_URL")
    client_kwargs = {"api_key": _get_env("OPENAI_API_KEY")}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)
    resp = client.chat.completions.create(
        model=_get_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content
    if content and content.strip():
        return content.strip()

    raise LLMResponseError("OpenAI khong tra ve noi dung van ban.")


def _call_huggingface(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    api_key = _get_env("HF_TOKEN") or _get_env("HUGGINGFACE_API_KEY")
    import requests

    base_url = _get_env("HUGGINGFACE_BASE_URL", HUGGINGFACE_BASE_URL).rstrip("/")
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _get_env("HUGGINGFACE_MODEL", DEFAULT_HUGGINGFACE_MODEL),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    content = payload["choices"][0]["message"]["content"]
    if content and content.strip():
        return content.strip()

    raise LLMResponseError("Hugging Face khong tra ve noi dung van ban.")


def call_llm(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    """
    Goi LLM theo provider cau hinh trong .env.
    temperature=0.0 cho SQL generation.
    temperature=0.3 cho answer synthesis.
    """
    provider = validate_llm_config()

    try:
        if provider == "groq":
            return _call_groq(user_prompt, system_prompt, temperature, max_tokens)
        if provider == "gemini":
            return _call_gemini(user_prompt, system_prompt, temperature, max_tokens)
        if provider == "openai":
            return _call_openai(user_prompt, system_prompt, temperature, max_tokens)
        return _call_huggingface(user_prompt, system_prompt, temperature, max_tokens)
    except Exception as e:
        logger.error(f"LLM call failed ({provider}): {e}")
        raise
