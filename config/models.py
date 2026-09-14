




# config/models.py

from __future__ import annotations

import os
from typing import Literal, Optional, Sequence

from dotenv import load_dotenv

from strands import Agent
from strands.models import ModelRouter
from strands.models.gemini import GeminiModel


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# TYPES
# ============================================================

ModelTier = Literal[
    "fast",
    "reasoning",
]


# ============================================================
# GEMINI MODEL POOLS
# ============================================================
#
# All inference in PURSUIT now runs THROUGH STRANDS.
#
# ModelRouter provides automatic fallback when a model fails
# because of:
#
# - quota limits
# - rate limits
# - provider errors
# - temporary availability problems
#
# ============================================================


# ------------------------------------------------------------
# Fast / high-volume tasks
#
# Used for:
# - Discovery extraction
# - Research extraction
# - JSON normalization
# - simpler structured tasks
# ------------------------------------------------------------

FAST_MODEL_IDS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]


# ------------------------------------------------------------
# Reasoning / judgment tasks
#
# Used for:
# - Personal Fit
# - Learning / Portfolio Value
# - Effort & Risk
# - Decision explanation
#
# Start with strongest Flash models first.
# ------------------------------------------------------------

REASONING_MODEL_IDS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


# ============================================================
# MODEL PARAMETERS
# ============================================================

FAST_MODEL_PARAMS = {
    "temperature": 0.1,
    "max_output_tokens": 8192,
}


REASONING_MODEL_PARAMS = {
    "temperature": 0.2,
    "max_output_tokens": 16384,
}


# ============================================================
# API KEY
# ============================================================

def get_gemini_api_key() -> str:
    """
    Return configured Gemini API key.

    Expected .env:

        GEMINI_API_KEY=...
    """

    api_key = (
        os.getenv(
            "GEMINI_API_KEY",
            "",
        )
        .strip()
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Add it to the .env file."
        )

    return api_key


# ============================================================
# SINGLE GEMINI MODEL
# ============================================================

def create_gemini_model(
    model_id: str,
    tier: ModelTier = "fast",
) -> GeminiModel:
    """
    Create one Strands GeminiModel.

    This is a STRANDS model provider, not a direct Gemini SDK
    call.
    """

    if tier == "reasoning":

        params = dict(
            REASONING_MODEL_PARAMS
        )

    else:

        params = dict(
            FAST_MODEL_PARAMS
        )

    return GeminiModel(
        client_args={
            "api_key":
                get_gemini_api_key(),
        },

        model_id=
            model_id,

        params=
            params,
    )


# ============================================================
# BUILD MODEL POOL
# ============================================================

def create_model_pool(
    tier: ModelTier,
) -> list[GeminiModel]:
    """
    Build ordered Strands model candidates.
    """

    if tier == "reasoning":

        model_ids = (
            REASONING_MODEL_IDS
        )

    else:

        model_ids = (
            FAST_MODEL_IDS
        )

    return [
        create_gemini_model(
            model_id=
                model_id,

            tier=
                tier,
        )

        for model_id
        in model_ids
    ]


# ============================================================
# STRANDS MODEL ROUTER
# ============================================================

def create_model_router(
    tier: ModelTier = "fast",
) -> ModelRouter:
    """
    Create a Strands ModelRouter.

    Fallback order follows the corresponding model list.

    Example:

        gemini-3.1-flash-lite
                ↓ failure
        gemini-3.5-flash-lite
                ↓ failure
        gemini-3.5-flash
                ↓
        ...
    """

    models = create_model_pool(
        tier
    )

    return ModelRouter(
        models=models,

        # Allow router to move through all candidates
        # during one failed invocation.
        max_switches=max(
            0,
            len(models) - 1,
        ),
    )


# ============================================================
# CREATE STRANDS AGENT
# ============================================================

def create_agent(
    tier: ModelTier = "fast",
    *,
    system_prompt: Optional[str] = None,
    tools: Optional[Sequence] = None,
) -> Agent:
    """
    Create a real Strands Agent.

    Every PURSUIT AI agent should ultimately use this helper.

    Parameters
    ----------
    tier:
        "fast" or "reasoning"

    system_prompt:
        Optional specialized agent identity/instructions.

    tools:
        Optional Strands tools available to the agent.

    Returns
    -------
    strands.Agent
    """

    router = create_model_router(
        tier
    )

    kwargs = {
        "model":
            router,
    }

    if system_prompt:
        kwargs[
            "system_prompt"
        ] = system_prompt

    if tools:
        kwargs[
            "tools"
        ] = list(
            tools
        )

    return Agent(
        **kwargs
    )


# ============================================================
# RUN THROUGH STRANDS
# ============================================================

def run_with_fallback(
    prompt: str,
    tier: ModelTier = "fast",
    *,
    system_prompt: Optional[str] = None,
    tools: Optional[Sequence] = None,
) -> str:
    """
    Execute a prompt THROUGH A REAL STRANDS AGENT.

    Existing PURSUIT agents already call:

        run_with_fallback(prompt, "fast")

    or:

        run_with_fallback(prompt, "reasoning")

    Therefore switching this implementation makes their
    inference Strands-powered without breaking the existing
    agent contracts.

    Model fallback itself is handled by Strands ModelRouter.
    """

    if not isinstance(
        prompt,
        str,
    ):
        raise TypeError(
            "prompt must be a string."
        )

    prompt = prompt.strip()

    if not prompt:
        raise ValueError(
            "prompt cannot be empty."
        )

    agent = create_agent(
        tier=tier,
        system_prompt=
            system_prompt,
        tools=
            tools,
    )

    try:

        response = agent(
            prompt
        )

    except Exception as exc:

        raise RuntimeError(
            "All Strands model candidates failed "
            f"for tier '{tier}': {exc}"
        ) from exc

    # Strands AgentResult has a useful string representation.
    text = str(
        response
    ).strip()

    if not text:
        raise RuntimeError(
            "Strands Agent returned an empty response."
        )

    return text


# ============================================================
# SPECIALIZED AGENT FACTORY
# ============================================================

def create_pursuit_agent(
    *,
    name: str,
    instructions: str,
    tier: ModelTier = "fast",
    tools: Optional[Sequence] = None,
) -> Agent:
    """
    Factory for PURSUIT's specialized Strands agents.

    Example:

        agent = create_pursuit_agent(
            name="Research Agent",
            instructions="Research opportunities...",
            tier="fast",
            tools=[fetch_opportunity],
        )

    The name is embedded into the system prompt so each agent
    has an explicit role.
    """

    name = str(
        name
    ).strip()

    instructions = str(
        instructions
    ).strip()

    system_prompt = f"""
You are PURSUIT's {name}.

{instructions}

You are one specialized agent inside PURSUIT's professional
opportunity intelligence system.

Be evidence-grounded.
Do not invent facts.
Follow the requested output contract exactly.
""".strip()

    return create_agent(
        tier=tier,
        system_prompt=
            system_prompt,
        tools=
            tools,
    )


# ============================================================
# DIAGNOSTICS
# ============================================================

def get_model_configuration() -> dict:
    """
    Safe diagnostic information for logs / README / debugging.

    API keys are NEVER returned.
    """

    return {
        "framework":
            "Strands Agents SDK",

        "provider":
            "Google Gemini",

        "fast_models":
            list(
                FAST_MODEL_IDS
            ),

        "reasoning_models":
            list(
                REASONING_MODEL_IDS
            ),

        "gemini_configured":
            bool(
                os.getenv(
                    "GEMINI_API_KEY"
                )
            ),

        "routing":
            "Strands ModelRouter / FallbackStrategy",
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print(
        "PURSUIT Strands model configuration:"
    )

    print(
        get_model_configuration()
    )

    print(
        "\nTesting Strands Agent..."
    )

    result = run_with_fallback(
        """
Return ONLY this JSON:

{
    "status": "ok",
    "framework": "Strands Agents SDK"
}
""",
        "fast",
    )

    print(
        "\nResult:"
    )

    print(
        result
    )


    