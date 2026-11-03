from __future__ import annotations

from dataclasses import dataclass

# Units are grouped by what they measure. A quantity can only be converted
# inside its own group (grams to kilograms, never grams to millilitres).
_FACTORS: dict[str, tuple[str, float]] = {
    "g": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "ml": ("volume", 1.0),
    "l": ("volume", 1000.0),
    "pcs": ("count", 1.0),
}


@dataclass(frozen=True)
class Quantity:
    amount: float
    unit: str

    def __post_init__(self) -> None:
        unit = self.unit.strip().lower()
        if unit not in _FACTORS:
            raise ValueError(f"unknown unit: {self.unit}")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        object.__setattr__(self, "unit", unit)

    def to(self, unit: str) -> Quantity:
        """Return the same amount expressed in another unit of the same kind."""
        target = unit.strip().lower()
        if target not in _FACTORS:
            raise ValueError(f"unknown unit: {unit}")
        kind, factor = _FACTORS[self.unit]
        target_kind, target_factor = _FACTORS[target]
        if kind != target_kind:
            raise ValueError(f"cannot convert {self.unit} to {target}")
        return Quantity(self.amount * factor / target_factor, target)

    def can_convert(self, unit: str) -> bool:
        target = unit.strip().lower()
        return target in _FACTORS and _FACTORS[target][0] == _FACTORS[self.unit][0]
