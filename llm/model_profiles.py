"""Model-aware audit profiles for chunked grading and review workflows."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AuditModelProfile:
    provider: str
    family: str
    label: str
    chunk_token_target: int
    max_packet_tokens: int
    overview_token_target: int
    recommended_passes: int
    structured_output_mode: str
    refusal_sensitivity: str
    hallucination_risk: str
    needs_explicit_rubric: bool
    needs_examples: bool
    estimated_tokens_per_second: float
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _detect_family(provider: str, model: str) -> str:
    name = (model or "").lower()
    if provider in {"openai", "github"}:
        if "mini" in name or "nano" in name:
            return "gpt_small"
        return "gpt_frontier"
    if provider == "anthropic":
        if "haiku" in name:
            return "claude_fast"
        if "opus" in name:
            return "claude_frontier"
        return "claude_balanced"
    if provider == "groq":
        if "gpt-oss" in name:
            return "groq_strict_json"
        if "llama-3.1-8b" in name or "8b" in name:
            return "groq_fast_small"
        return "groq_large"
    if provider == "mistral":
        if "codestral" in name or "devstral" in name:
            return "mistral_code"
        if "small" in name or "ministral" in name:
            return "mistral_small"
        return "mistral_large"
    if provider == "together":
        if "70b" in name or "72b" in name:
            return "together_large"
        return "together_small"
    if provider == "huggingface":
        return "hf_open"
    if provider in {"ollama", "lmstudio"}:
        if any(tag in name for tag in ("3b", "mini", "phi3:mini", "qwen2.5:3b")):
            return "local_tiny"
        if any(tag in name for tag in ("7b", "8b", "9b", "12b", "14b", "phi3:medium")):
            return "local_mid"
        return "local_large"
    return "generic"


PROFILE_DEFAULTS = {
    "gpt_frontier": AuditModelProfile(
        provider="openai",
        family="gpt_frontier",
        label="GPT frontier",
        chunk_token_target=5000,
        max_packet_tokens=9000,
        overview_token_target=12000,
        recommended_passes=2,
        structured_output_mode="strict_schema",
        refusal_sensitivity="medium",
        hallucination_risk="low",
        needs_explicit_rubric=True,
        needs_examples=False,
        estimated_tokens_per_second=180.0,
        notes=(
            "Strong long-context and structured output support.",
            "Still treat JSON validity and semantic grading accuracy as separate checks.",
        ),
    ),
    "gpt_small": AuditModelProfile(
        provider="openai",
        family="gpt_small",
        label="GPT small",
        chunk_token_target=2200,
        max_packet_tokens=4000,
        overview_token_target=5000,
        recommended_passes=2,
        structured_output_mode="strict_schema",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=260.0,
        notes=(
            "Prefer narrower packets and explicit success criteria.",
            "Use second-pass verification on borderline grading decisions.",
        ),
    ),
    "claude_frontier": AuditModelProfile(
        provider="anthropic",
        family="claude_frontier",
        label="Claude frontier",
        chunk_token_target=4500,
        max_packet_tokens=8000,
        overview_token_target=12000,
        recommended_passes=2,
        structured_output_mode="prompted_json",
        refusal_sensitivity="high",
        hallucination_risk="low",
        needs_explicit_rubric=True,
        needs_examples=False,
        estimated_tokens_per_second=110.0,
        notes=(
            "Strong long-context reasoning but naturally verbose.",
            "Use concise schema instructions and constrain output length for grading packets.",
        ),
    ),
    "claude_balanced": AuditModelProfile(
        provider="anthropic",
        family="claude_balanced",
        label="Claude balanced",
        chunk_token_target=3200,
        max_packet_tokens=6000,
        overview_token_target=9000,
        recommended_passes=2,
        structured_output_mode="prompted_json",
        refusal_sensitivity="high",
        hallucination_risk="low",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=130.0,
        notes=(
            "Use explicit output keys and short grading language.",
            "Strong at nuanced feedback but can over-explain unless constrained.",
        ),
    ),
    "claude_fast": AuditModelProfile(
        provider="anthropic",
        family="claude_fast",
        label="Claude fast",
        chunk_token_target=1800,
        max_packet_tokens=3200,
        overview_token_target=4200,
        recommended_passes=2,
        structured_output_mode="prompted_json",
        refusal_sensitivity="high",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=180.0,
        notes=(
            "Prefer many small packets over one large overview.",
            "Use a second pass for strict course-completion judgments.",
        ),
    ),
    "groq_strict_json": AuditModelProfile(
        provider="groq",
        family="groq_strict_json",
        label="Groq strict-json",
        chunk_token_target=2500,
        max_packet_tokens=5000,
        overview_token_target=7000,
        recommended_passes=2,
        structured_output_mode="strict_schema",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=False,
        estimated_tokens_per_second=450.0,
        notes=(
            "Strict structured outputs are only supported on a subset of Groq models.",
            "Streaming and tool use are not available with Groq structured outputs.",
        ),
    ),
    "groq_fast_small": AuditModelProfile(
        provider="groq",
        family="groq_fast_small",
        label="Groq fast small",
        chunk_token_target=1400,
        max_packet_tokens=2600,
        overview_token_target=3600,
        recommended_passes=3,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=560.0,
        notes=(
            "Use JSON object mode or prompt-constrained JSON, not schema trust.",
            "Favor repeated atomic passes because speed is high and packets are cheap.",
        ),
    ),
    "groq_large": AuditModelProfile(
        provider="groq",
        family="groq_large",
        label="Groq large",
        chunk_token_target=2600,
        max_packet_tokens=5000,
        overview_token_target=7000,
        recommended_passes=2,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=280.0,
        notes=(
            "Fast enough for multi-pass audits, but JSON semantics still need validation.",
            "Use smaller packet boundaries than frontier closed models.",
        ),
    ),
    "mistral_large": AuditModelProfile(
        provider="mistral",
        family="mistral_large",
        label="Mistral large",
        chunk_token_target=2800,
        max_packet_tokens=5200,
        overview_token_target=7600,
        recommended_passes=2,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=120.0,
        notes=(
            "Model families differ widely; do not assume one Mistral prompt fits all variants.",
            "Use rubric-led extraction and explicit field constraints.",
        ),
    ),
    "mistral_small": AuditModelProfile(
        provider="mistral",
        family="mistral_small",
        label="Mistral small",
        chunk_token_target=1400,
        max_packet_tokens=2600,
        overview_token_target=3200,
        recommended_passes=3,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=90.0,
        notes=(
            "Use packetized grading with retries and local validation.",
            "Small open models need narrower evidence slices for reliable review.",
        ),
    ),
    "mistral_code": AuditModelProfile(
        provider="mistral",
        family="mistral_code",
        label="Mistral code specialist",
        chunk_token_target=2200,
        max_packet_tokens=4200,
        overview_token_target=5200,
        recommended_passes=2,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=False,
        estimated_tokens_per_second=130.0,
        notes=(
            "Use for code-centric packets, not broad academic synthesis.",
            "Separate code grading from essay-style reasoning packets when possible.",
        ),
    ),
    "together_large": AuditModelProfile(
        provider="together",
        family="together_large",
        label="Together large open model",
        chunk_token_target=2200,
        max_packet_tokens=4200,
        overview_token_target=6000,
        recommended_passes=2,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=120.0,
        notes=(
            "Use conservative packet sizing because model behavior varies by hosted family.",
            "Prefer repeated atomic grading over single-pass holistic judgment.",
        ),
    ),
    "together_small": AuditModelProfile(
        provider="together",
        family="together_small",
        label="Together small open model",
        chunk_token_target=1200,
        max_packet_tokens=2200,
        overview_token_target=3000,
        recommended_passes=3,
        structured_output_mode="json_object",
        refusal_sensitivity="medium",
        hallucination_risk="high",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=100.0,
        notes=(
            "Tiny and mid-size hosted open models need narrow packets and retry guards.",
            "Never trust a single high-level completion for final course eligibility.",
        ),
    ),
    "hf_open": AuditModelProfile(
        provider="huggingface",
        family="hf_open",
        label="HuggingFace open model",
        chunk_token_target=1000,
        max_packet_tokens=1800,
        overview_token_target=2400,
        recommended_passes=3,
        structured_output_mode="prompted_json",
        refusal_sensitivity="medium",
        hallucination_risk="high",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=80.0,
        notes=(
            "Treat as prompt-only structured output unless the endpoint proves stronger guarantees.",
            "Use aggressive chunking and deterministic rubrics.",
        ),
    ),
    "local_tiny": AuditModelProfile(
        provider="ollama",
        family="local_tiny",
        label="Local tiny model",
        chunk_token_target=700,
        max_packet_tokens=1200,
        overview_token_target=1600,
        recommended_passes=4,
        structured_output_mode="prompted_json",
        refusal_sensitivity="low",
        hallucination_risk="high",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=28.0,
        notes=(
            "Use atomic packets only.",
            "Require schema validation and verification passes because semantic drift is common.",
        ),
    ),
    "local_mid": AuditModelProfile(
        provider="ollama",
        family="local_mid",
        label="Local mid model",
        chunk_token_target=1200,
        max_packet_tokens=2200,
        overview_token_target=3000,
        recommended_passes=3,
        structured_output_mode="prompted_json",
        refusal_sensitivity="low",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=16.0,
        notes=(
            "Good target for low-cost repeated grading passes.",
            "Keep course overviews short and put evidence in packet form.",
        ),
    ),
    "local_large": AuditModelProfile(
        provider="ollama",
        family="local_large",
        label="Local large model",
        chunk_token_target=2000,
        max_packet_tokens=3600,
        overview_token_target=4800,
        recommended_passes=2,
        structured_output_mode="prompted_json",
        refusal_sensitivity="low",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=False,
        estimated_tokens_per_second=8.0,
        notes=(
            "Bigger local models can review broader packets but still benefit from chunk-first audits.",
            "ETA must account for user hardware and configured context length.",
        ),
    ),
    "generic": AuditModelProfile(
        provider="generic",
        family="generic",
        label="Generic model",
        chunk_token_target=1200,
        max_packet_tokens=2200,
        overview_token_target=3200,
        recommended_passes=3,
        structured_output_mode="prompted_json",
        refusal_sensitivity="medium",
        hallucination_risk="medium",
        needs_explicit_rubric=True,
        needs_examples=True,
        estimated_tokens_per_second=80.0,
        notes=(
            "Default to conservative packet size and explicit JSON keys.",
            "Use multi-pass review for any consequential academic decision.",
        ),
    ),
}


def resolve_audit_profile(provider: str, model: str) -> AuditModelProfile:
    family = _detect_family(provider, model)
    profile = PROFILE_DEFAULTS.get(family, PROFILE_DEFAULTS["generic"])
    if provider in {"lmstudio"} and profile.provider == "ollama":
        return AuditModelProfile(
            provider=provider,
            family=profile.family,
            label=profile.label.replace("Local", "LM Studio"),
            chunk_token_target=profile.chunk_token_target,
            max_packet_tokens=profile.max_packet_tokens,
            overview_token_target=profile.overview_token_target,
            recommended_passes=profile.recommended_passes,
            structured_output_mode=profile.structured_output_mode,
            refusal_sensitivity=profile.refusal_sensitivity,
            hallucination_risk=profile.hallucination_risk,
            needs_explicit_rubric=profile.needs_explicit_rubric,
            needs_examples=profile.needs_examples,
            estimated_tokens_per_second=profile.estimated_tokens_per_second,
            notes=profile.notes,
        )
    return profile


def estimate_audit_seconds(provider: str, model: str, token_count: int, passes: int | None = None) -> int:
    profile = resolve_audit_profile(provider, model)
    total_passes = passes if passes is not None else profile.recommended_passes
    total_tokens = max(token_count * max(total_passes, 1), 1)
    tps = max(profile.estimated_tokens_per_second, 1.0)
    return int(total_tokens / tps)


def build_audit_prompt_constraints(provider: str, model: str) -> str:
    profile = resolve_audit_profile(provider, model)
    lines = [
        f"Model profile: {profile.label}.",
        f"Packet budget: keep reasoning tied to the provided evidence packet and under {profile.max_packet_tokens} input tokens.",
        "Do not infer missing evidence. If the packet does not prove something, mark it insufficient.",
        "Prefer a harsh but fair academic standard. Do not inflate borderline work.",
    ]
    if profile.needs_explicit_rubric:
        lines.append("Follow the rubric literally and score each criterion explicitly.")
    if profile.needs_examples:
        lines.append("Prefer simple output keys and short field values to reduce schema drift.")
    if profile.structured_output_mode == "strict_schema":
        lines.append("Schema compliance is expected, but semantic accuracy still matters more than pretty JSON.")
    else:
        lines.append("JSON shape is best-effort only. If uncertain, choose the conservative grade and explain why.")
    return "\n".join(lines)