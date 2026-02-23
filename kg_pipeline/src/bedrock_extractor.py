"""
AWS Bedrock extraction backend for the KG pipeline.
Replaces Gemini when extract.model starts with "bedrock/" (e.g. "bedrock/amazon.nova-micro-v1:0").

Supported on-demand models (as of 2026):
  bedrock/amazon.nova-micro-v1:0   — $0.035/$0.14 per 1M tokens  (cheapest; text-only)
  bedrock/amazon.nova-lite-v1:0    — $0.06/$0.24 per 1M tokens   (multimodal; good for complex papers)
  bedrock/anthropic.claude-3-haiku-20240307-v1:0 — $0.25/$1.25   (highest accuracy)

Batch Inference (50% off):
  Use batch/amazon.nova-micro-v1:0 prefix to submit as Bedrock batch job (async; no real-time SLA).
  Results written to S3; add AWS_BATCH_OUTPUT_BUCKET to kg_pipeline/.env to enable.

Usage in config.yaml:
  extract:
    model: "bedrock/amazon.nova-micro-v1:0"   # cheapest
    # model: "bedrock/amazon.nova-lite-v1:0"  # better for tables/complex papers
    # model: "bedrock/anthropic.claude-3-haiku-20240307-v1:0"  # highest accuracy
    bedrock_region: "us-east-1"               # optional; default: us-east-1
"""
import json
import os
import time
from typing import Any


# ── Lazy client singleton ─────────────────────────────────────────────────────

_bedrock_client: Any = None


def _get_client(region: str = "us-east-1"):
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        _bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_client


# ── Model routing ─────────────────────────────────────────────────────────────

def _is_nova(model_id: str) -> bool:
    return "nova" in model_id.lower()


def _is_claude(model_id: str) -> bool:
    return "anthropic" in model_id.lower() or "claude" in model_id.lower()


# ── Invocation ────────────────────────────────────────────────────────────────

def _invoke_converse(client, model_id: str, prompt: str, max_tokens: int = 4096) -> str:
    """
    Use Bedrock Converse API — works with both Nova and Claude models.
    Returns the text response string.
    """
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.1},
    )
    # Converse response: output.message.content[0].text
    return response["output"]["message"]["content"][0]["text"]


def extract_triples_bedrock(
    prompt: str,
    model_id: str,
    pmcid: str,
    region: str = "us-east-1",
    max_retries: int = 3,
) -> list[dict]:
    """
    Send extraction prompt to a Bedrock model, parse JSON triple list.
    Handles throttling with exponential backoff.

    Args:
        prompt:    The full extraction prompt (same format as Gemini variant).
        model_id:  Bare Bedrock model ID (e.g. "amazon.nova-micro-v1:0").
        pmcid:     Paper ID, used only for logging.
        region:    AWS region.
        max_retries: Number of retry attempts on throttling.

    Returns:
        List of triple dicts, or [] on failure.
    """
    client = _get_client(region)
    print(f"Sending extraction request to Bedrock ({model_id}) for {pmcid}...")

    for attempt in range(max_retries):
        try:
            raw = _invoke_converse(client, model_id, prompt)

            # Strip any prose prefix and markdown code fences.
            # Nova Micro sometimes returns: "Here is the JSON...\n\n```json\n[...]```"
            text = raw.strip()
            fence_pos = text.find("```")
            if fence_pos != -1:
                text = text[fence_pos:]          # drop any prose before the fence
                text = text.split("```", 2)[1]   # drop opening fence
                if text.startswith("json"):
                    text = text[4:]
                text = text.rsplit("```", 1)[0].strip()
            # If no fence but starts with [ or {, use as-is
            elif not (text.startswith("[") or text.startswith("{")):
                # Try to find the start of the JSON array/object
                bracket = min(
                    (text.find("[") if text.find("[") != -1 else len(text)),
                    (text.find("{") if text.find("{") != -1 else len(text)),
                )
                text = text[bracket:].strip()

            # Fix invalid escape sequences (e.g. 2\'-FL → 2'-FL) before parsing
            import re as _re
            text = _re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
            triples = json.loads(text)
            if not isinstance(triples, list):
                print(f"Unexpected response shape for {pmcid}: {type(triples)}")
                return []
            return triples

        except client.exceptions.ThrottlingException as e:
            wait = 2 ** (attempt + 2)  # 4s, 8s, 16s
            print(f"Bedrock throttled for {pmcid}. Retrying in {wait}s... (Attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        except json.JSONDecodeError as e:
            print(f"JSON parse error for {pmcid}: {e}. Raw response (first 200): {raw[:200]}")
            return []
        except Exception as e:
            # Catch-all for boto3 client errors (access denied, model not found, etc.)
            err = str(e)
            if "ThrottlingException" in err or "TooManyRequests" in err:
                wait = 2 ** (attempt + 2)
                print(f"Bedrock throttled for {pmcid}. Retrying in {wait}s...")
                time.sleep(wait)
                continue
            if "AccessDeniedException" in err:
                print(f"Bedrock access denied for model {model_id}. Check IAM permissions or model access in us-east-1.")
            elif "ValidationException" in err and "model" in err.lower():
                print(f"Invalid Bedrock model ID: {model_id}. Check config.yaml extract.model.")
            else:
                print(f"Bedrock error for {pmcid}: {e}")
            return []

    print(f"Bedrock: max retries exceeded for {pmcid}.")
    return []


# ── Inter-paper delay recommendation ─────────────────────────────────────────

# Bedrock on-demand has much higher rate limits than Gemini free tier.
# Recommended delays (seconds) for batch processing without provisioned throughput:
RECOMMENDED_DELAY: dict[str, int] = {
    "amazon.nova-micro-v1:0": 1,   # Very high RPM; minimal delay needed
    "amazon.nova-lite-v1:0": 1,
    "anthropic.claude-3-haiku-20240307-v1:0": 2,
}

DEFAULT_DELAY = 2


def get_recommended_delay(model_id: str) -> int:
    return RECOMMENDED_DELAY.get(model_id, DEFAULT_DELAY)
