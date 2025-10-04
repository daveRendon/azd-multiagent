"""Utility script to verify deployed Azure AI agents can process a ticket."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Iterable, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


SUCCESS_STATUSES = {
    "succeeded",
    "completed",
}

TERMINAL_FAILURE_STATUSES = {
    "failed",
    "canceled",
}

TERMINAL_STATUSES = SUCCESS_STATUSES | TERMINAL_FAILURE_STATUSES


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Environment variable '{name}' is required. "
            "Run `azd env get-values` to copy it into your shell before retrying."
        )
    return value.strip()


def _normalize_status(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    # Convert enum-like forms such as "RunStatus.IN_PROGRESS" to "in_progress"
    if "." in text:
        text = text.split(".")[-1]
    return text.strip().lower()


def _is_retryable_rate_limit(error: Optional[object]) -> bool:
    if not error:
        return False
    if isinstance(error, dict):
        code = str(error.get("code", "")).lower()
        message = str(error.get("message", "")).lower()
    else:
        code = ""
        message = str(error).lower()
    return "rate_limit" in code or "rate limit" in message


def _serialize_error(error: Optional[object]) -> Optional[object]:
    if error is None:
        return None
    if hasattr(error, "to_dict"):
        try:
            return error.to_dict()
        except Exception:
            pass
    if hasattr(error, "as_dict"):
        try:
            return error.as_dict()  # type: ignore[return-value]
        except Exception:
            pass
    if hasattr(error, "__dict__"):
        try:
            return dict(error.__dict__)
        except Exception:
            pass
    return str(error)


def verify_agent(
    ticket: str,
    poll_interval: float,
    timeout: float,
    max_attempts: int,
    initial_backoff: float,
    max_backoff: float,
    agent_id: str,
) -> dict:
    endpoint = _require_env("AIFOUNDRY_PROJECT_ENDPOINT")

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    agents_client = project_client.agents

    print(f"Using project endpoint: {endpoint!r}")
    print(f"Using agent id: {agent_id}")

    try:
        thread = agents_client.threads.create()
    except Exception as exc:  # pragma: no cover - investigative logging
        print(f"failed to create thread: {exc}", file=sys.stderr)
        raise

    try:
        agents_client.messages.create(thread_id=thread.id, role="user", content=ticket)
    except Exception as exc:  # pragma: no cover - investigative logging
        print(f"failed to create message: {exc}", file=sys.stderr)
        raise

    attempt = 1
    base_backoff = max(initial_backoff, poll_interval * 2)
    current_backoff = base_backoff

    while attempt <= max_attempts:
        try:
            run = agents_client.runs.create(thread_id=thread.id, agent_id=agent_id)
        except Exception as exc:  # pragma: no cover - investigative logging
            print(f"failed to create run: {exc}", file=sys.stderr)
            raise

        deadline = time.time() + timeout
        last_status: Optional[str] = None
        last_error: Optional[object] = None
        retry_requested = False
        while time.time() < deadline:
            current_run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
            status_value = _normalize_status(getattr(current_run, "status", None))
            last_status = status_value
            if status_value:
                print(f"status: {status_value}")
            if status_value in TERMINAL_STATUSES:
                last_error = _serialize_error(getattr(current_run, "last_error", None))
                if status_value in SUCCESS_STATUSES:
                    return {
                        "thread_id": thread.id,
                        "run_id": run.id,
                        "status": status_value,
                        "last_error": last_error,
                        "succeeded": True,
                        "project_endpoint": endpoint,
                    }
                if _is_retryable_rate_limit(last_error) and attempt < max_attempts:
                    wait_seconds = min(max_backoff, current_backoff)
                    print(
                        f"Run attempt {attempt} failed due to rate limit; retrying after {wait_seconds:.0f}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)
                    current_backoff = min(max_backoff, current_backoff * 1.5)
                    retry_requested = True
                    attempt += 1
                    break
                return {
                    "thread_id": thread.id,
                    "run_id": run.id,
                    "status": status_value,
                    "last_error": last_error,
                    "succeeded": False,
                    "project_endpoint": endpoint,
                }
            time.sleep(poll_interval)
        else:
            # loop exited without break => timeout
            raise TimeoutError(
                f"Timed out waiting for run {run.id} (last status: {last_status or 'unknown'})."
            )

        if retry_requested:
            continue

    raise RuntimeError("Exceeded retry attempts due to repeated rate limiting.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify the triage agent responds to a ticket.")
    parser.add_argument(
        "--ticket",
        default="VPN outage affecting finance team",
        help="Ticket text to send to the agent.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between status checks (default: 2.0).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Maximum seconds to wait for completion (default: 120).",
    )
    parser.add_argument(
        "--show-transcript",
        action="store_true",
        help="Print the thread messages returned by the agent after completion.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Maximum number of run attempts when rate limited (default: 5).",
    )
    parser.add_argument(
        "--initial-backoff",
        type=float,
        default=7.0,
        help="Initial backoff seconds after rate limiting (default: 7).",
    )
    parser.add_argument(
        "--max-backoff",
        type=float,
        default=30.0,
        help="Maximum backoff seconds between retries (default: 30).",
    )
    parser.add_argument(
        "--agent-id",
        help="Override the agent identifier (default: TRIAGE_AGENT_ID environment variable).",
    )

    args = parser.parse_args(argv)
    agent_id = args.agent_id or _require_env("TRIAGE_AGENT_ID")

    try:
        result = verify_agent(
            ticket=args.ticket,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
            initial_backoff=args.initial_backoff,
            max_backoff=args.max_backoff,
            agent_id=agent_id,
        )
    except (HttpResponseError, TimeoutError, SystemExit) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected failure surface
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 1

    if args.show_transcript:
        print("\n--- Agent transcript ---")
        try:
            for line in _iter_thread_messages(endpoint=result["project_endpoint"], thread_id=result["thread_id"]):
                print(line)
        except Exception as exc:  # pragma: no cover - diagnostic aid
            print(f"failed to read thread transcript: {exc}", file=sys.stderr)

    print(json.dumps(result, indent=2))
    if not result.get("succeeded", False):
        print("Agent run did not succeed.", file=sys.stderr)
        return 2

    print("Agent verification succeeded.")
    return 0


def _iter_thread_messages(*, endpoint: str, thread_id: str) -> Iterable[str]:
    project_client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    agents_client = project_client.agents
    messages = agents_client.messages.list(thread_id=thread_id)
    for message in messages:
        role = getattr(message, "role", "unknown")
        parts = []
        for item in getattr(message, "content", []) or []:
            text = getattr(item, "text", None)
            if text is not None:
                value = getattr(text, "value", text)
                if value:
                    parts.append(str(value))
                continue
            # Fallback to common attributes such as "input_text" or "content".
            value = None
            for attr in ("input_text", "content", "value"):
                if hasattr(item, attr):
                    candidate = getattr(item, attr)
                    if candidate:
                        value = candidate
                        break
            if value:
                parts.append(str(value))
        body = "\n".join(parts) if parts else "<no text content>"
        yield f"[{role}] {body}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
