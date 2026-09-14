




import json


def parse_llm_json(response):
    """
    Parse JSON returned by an LLM.

    Handles:
    - plain JSON
    - ```json fences
    - ``` fences
    - small amounts of text before/after JSON
    """

    text = str(response).strip()

    # Remove markdown fences.
    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    # First try normal JSON parsing.
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Fallback: extract first complete-looking JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No valid JSON object found in model response:\n{text}"
        )

    json_text = text[
        start:end + 1
    ]

    return json.loads(
        json_text
    )



