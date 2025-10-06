import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from verify_agent import (
    verify_agent as run_agent_verification,
    _iter_thread_messages,
)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    print(f"Loading environment values from {path}")
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_quotes(value)
            existing = os.environ.get(key)
            if existing and existing != value:
                print(f"Overriding environment variable {key} (was '{existing}', now '{value}')")
            os.environ[key] = value


def _detect_azd_env_name() -> Optional[str]:
    explicit = os.getenv("AZURE_ENV_NAME")
    if explicit:
        return explicit

    config_path = Path(".azure") / "config.json"
    if not config_path.exists():
        return None
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    candidates = []
    defaults = data.get("defaults", {})
    candidates.append(defaults.get("environment"))
    candidates.append(data.get("defaultEnvironment"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _initialize_env(explicit_path: Optional[str]) -> None:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    azure_env = _detect_azd_env_name()
    if azure_env:
        candidates.append(Path(".azure") / azure_env / ".env")
    candidates.append(Path(".env"))

    for candidate in candidates:
        try:
            _load_env_file(candidate)
        except OSError as exc:
            print(f"Warning: failed to read {candidate}: {exc}")

    if "AIFOUNDRY_PROJECT_ENDPOINT" not in os.environ:
        alt_endpoint = os.environ.get("projectEndpoint") or os.environ.get("PROJECT_ENDPOINT")
        if alt_endpoint:
            os.environ["AIFOUNDRY_PROJECT_ENDPOINT"] = alt_endpoint


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Environment variable '{name}' is required to test agents. "
            "Run `azd env get-values` and export it before retrying."
        )
    return value.strip()


def _extract_agent_lines(transcript: List[str]) -> List[str]:
    agent_lines: List[str] = []
    for line in transcript:
        if "MessageRole.AGENT" in line or line.lower().startswith("[assistant]"):
            agent_lines.append(line)
    return agent_lines or transcript


def test_agents(ticket: str, poll_interval: float, timeout: float, max_attempts: int, initial_backoff: float, max_backoff: float) -> Dict[str, List[str]]:
    endpoint = _require_env("AIFOUNDRY_PROJECT_ENDPOINT")

    agent_env_map = {
        "priority": "PRIORITY_AGENT_ID",
        "team": "TEAM_AGENT_ID",
        "effort": "EFFORT_AGENT_ID",
        "triage": "TRIAGE_AGENT_ID",
    }

    outputs: Dict[str, List[str]] = {}

    for agent_name, env_var in agent_env_map.items():
        agent_id = _require_env(env_var)
        print(f"\nRunning {agent_name} agent ({agent_id})...")
        result = run_agent_verification(
            ticket=ticket,
            poll_interval=poll_interval,
            timeout=timeout,
            max_attempts=max_attempts,
            initial_backoff=initial_backoff,
            max_backoff=max_backoff,
            agent_id=agent_id,
        )
        transcript = list(_iter_thread_messages(endpoint=result["project_endpoint"], thread_id=result["thread_id"]))
        outputs[agent_name] = _extract_agent_lines(transcript)

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all support agents and print their outputs.")
    parser.add_argument("--ticket", default="VPN outage affecting finance team", help="Ticket text to evaluate.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between status checks (default: 2.0).")
    parser.add_argument("--timeout", type=float, default=120.0, help="Maximum seconds to wait per run (default: 120).")
    parser.add_argument("--max-attempts", type=int, default=12, help="Maximum run attempts when rate limited (default: 12).")
    parser.add_argument("--initial-backoff", type=float, default=12.0, help="Initial backoff seconds after rate limiting (default: 12).")
    parser.add_argument("--max-backoff", type=float, default=60.0, help="Maximum backoff seconds between retries (default: 60).")
    parser.add_argument("--env-file", help="Optional path to an env file to load before running tests.")

    args = parser.parse_args()

    _initialize_env(args.env_file)

    outputs = test_agents(
        ticket=args.ticket,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        initial_backoff=args.initial_backoff,
        max_backoff=args.max_backoff,
    )

    print("\n=== Consolidated Agent Responses ===")
    for agent_name, lines in outputs.items():
        print(f"\n[{agent_name.upper()}]")
        for line in lines:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
