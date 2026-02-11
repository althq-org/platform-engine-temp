"""Validate platform.yaml against the JSON Schema for the declared apiVersion."""

import json
from pathlib import Path

import jsonschema


def _schema_dir() -> Path:
    """Directory containing schema files (devops/schema/)."""
    return Path(__file__).resolve().parent.parent / "schema"


def load_schema(api_version: str) -> dict:
    """Load the JSON Schema for the given apiVersion.

    apiVersion format is e.g. 'platform.althq.com/v1'.
    Schema file is named from the last segment, e.g. platform-spec-v1.json.
    """
    if api_version == "platform.althq.com/v1":
        name = "platform-spec-v1.json"
    else:
        raise ValueError(f"Unsupported apiVersion: {api_version}")
    path = _schema_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_platform_spec(data: dict) -> None:
    """Validate a parsed platform.yaml (dict) against its apiVersion schema.

    Raises:
        jsonschema.ValidationError: If validation fails. Message includes
            all error details. Caller may convert to SystemExit for CLI.
    """
    api_version = data.get("apiVersion")
    if not api_version:
        raise jsonschema.ValidationError("Missing required field: apiVersion")
    schema = load_schema(api_version)
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        lines = ["platform.yaml validation failed:"]
        for i, err in enumerate(errors[:10], 1):
            path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
            lines.append(f"  {i}. {path}: {err.message}")
        if len(errors) > 10:
            lines.append(f"  ... and {len(errors) - 10} more errors")
        raise jsonschema.ValidationError("\n".join(lines))
