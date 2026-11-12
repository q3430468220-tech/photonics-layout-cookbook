"""Foundry process adapters: role -> GDS layer, vertical stack, materials, doping."""

from photonics_cookbook.process.model import (
    LAYER_KINDS,
    STANDARD_ROLES,
    BackgroundLayer,
    Material,
    Process,
    ProcessError,
    ProcessLayer,
    available_processes,
    load_process,
    validate_process,
)

__all__ = [
    "LAYER_KINDS",
    "STANDARD_ROLES",
    "BackgroundLayer",
    "Material",
    "Process",
    "ProcessError",
    "ProcessLayer",
    "available_processes",
    "load_process",
    "validate_process",
]
