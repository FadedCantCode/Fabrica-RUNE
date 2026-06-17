"""
rune_loader.py — Parses and validates .rune files per RFC-0001.
"""
import yaml
from dataclasses import dataclass, field
from typing import List, Dict


SUPPORTED_SCHEMA_MAJOR = "0"

KNOWN_STEPS = {"search", "analyze", "summarize", "code", "test"}
KNOWN_CONSTRAINTS = {"cite_sources", "structured_output"}
KNOWN_BEHAVIOR_KEYS = {"curiosity"}


class RuneValidationError(Exception):
    pass


@dataclass
class Rune:
    species: str
    version: str
    description: str
    genome: List[str]
    tools: List[str]
    constraints: List[str] = field(default_factory=list)
    behavior: Dict[str, float] = field(default_factory=dict)

    @property
    def temperature(self) -> float:
        """Map behavior.curiosity [0,1] -> sampling temperature [0,1.2]."""
        curiosity = self.behavior.get("curiosity", 0.5)
        return round(curiosity * 1.2, 2)


def load_rune(path: str) -> Rune:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _validate(data, path)

    return Rune(
        species=data["species"],
        version=data["version"],
        description=data.get("description", "").strip(),
        genome=data["genome"],
        tools=data.get("tools") or [],
        constraints=data.get("constraints") or [],
        behavior=data.get("behavior") or {},
    )


def _validate(data: dict, path: str) -> None:
    if not isinstance(data, dict):
        raise RuneValidationError(f"{path}: top-level document must be a mapping")

    for required in ("species", "version", "genome"):
        if required not in data:
            raise RuneValidationError(f"{path}: missing required field '{required}'")

    version = str(data["version"])
    major = version.split(".")[0]
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise RuneValidationError(
            f"{path}: schema version {version} has unsupported major version "
            f"'{major}' (this runtime supports major version {SUPPORTED_SCHEMA_MAJOR}.x)"
        )

    genome = data["genome"]
    if not isinstance(genome, list) or not genome:
        raise RuneValidationError(f"{path}: 'genome' must be a non-empty list")

    unknown_steps = set(genome) - KNOWN_STEPS
    if unknown_steps:
        raise RuneValidationError(
            f"{path}: genome contains unsupported step(s): {sorted(unknown_steps)}. "
            f"Known steps: {sorted(KNOWN_STEPS)}"
        )

    tools = data.get("tools") or []
    if "search" in genome and "search" not in tools:
        raise RuneValidationError(
            f"{path}: genome includes 'search' step but 'search' is not in 'tools' allowlist"
        )

    constraints = data.get("constraints") or []
    unknown_constraints = set(constraints) - KNOWN_CONSTRAINTS
    if unknown_constraints:
        raise RuneValidationError(
            f"{path}: unsupported constraint(s): {sorted(unknown_constraints)}. "
            f"Known constraints: {sorted(KNOWN_CONSTRAINTS)}"
        )

    behavior = data.get("behavior") or {}
    for key, val in behavior.items():
        if key not in KNOWN_BEHAVIOR_KEYS:
            raise RuneValidationError(f"{path}: unsupported behavior key '{key}'")
        if not (0.0 <= float(val) <= 1.0):
            raise RuneValidationError(f"{path}: behavior.{key} must be in [0.0, 1.0], got {val}")
