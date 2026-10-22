"""Measurement units. Storage is always centimeters with one decimal."""

from enum import StrEnum

CM_PER_IN = 2.54


class Unit(StrEnum):
    IN = "in"
    CM = "cm"


def to_cm(value: float, unit: Unit) -> float:
    return round(value * CM_PER_IN if unit is Unit.IN else value, 1)


def from_cm(value_cm: float, unit: Unit) -> float:
    return round(value_cm / CM_PER_IN if unit is Unit.IN else value_cm, 1)
