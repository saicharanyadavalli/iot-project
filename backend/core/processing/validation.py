"""Sensor data validation and physical safety limits checking.
Validates numeric integrity, bounds, missing fields, NaN/inf,
and identifies physical safety threshold violations.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from config.settings import SafetyThresholds, NormalizationBounds


@dataclass
class ValidationResult:
    """Detailed result of sensor validation checks."""
    is_valid: bool
    is_within_bounds: bool
    is_safety_violation: bool
    errors: List[str]
    safety_violations: List[str]
    out_of_bounds_fields: List[str]

    @property
    def has_issues(self) -> bool:
        return not self.is_valid or self.is_safety_violation or not self.is_within_bounds


class SensorValidator:
    """Validates raw sensor data and checks against physical safety limits."""

    def __init__(self, safety: SafetyThresholds, normalization: NormalizationBounds):
        self.safety = safety
        self.normalization = normalization

    def validate_reading_value(self, name: str, value: Any) -> tuple[bool, Optional[str]]:
        """Check if a numeric sensor value is present, float/int, and neither NaN nor Infinite."""
        if value is None:
            return False, f"Missing value for {name}"
        if not isinstance(value, (int, float)):
            return False, f"Value for {name} must be numeric, got {type(value).__name__}"
        if math.isnan(value):
            return False, f"Value for {name} is NaN"
        if math.isinf(value):
            return False, f"Value for {name} is Infinite"
        return True, None

    def check_safety_limits(self, temp: Optional[float], ph: Optional[float], tds: Optional[float]) -> List[str]:
        """Check if any available parameter violates physical operating safety thresholds."""
        violations = []
        if temp is not None:
            if temp < self.safety.temp_min:
                violations.append(f"Temperature ({temp:.2f}°C) below safety limit ({self.safety.temp_min}°C)")
            elif temp > self.safety.temp_max:
                violations.append(f"Temperature ({temp:.2f}°C) exceeds safety limit ({self.safety.temp_max}°C)")

        if ph is not None:
            if ph < self.safety.ph_min:
                violations.append(f"pH ({ph:.2f}) below safety limit ({self.safety.ph_min})")
            elif ph > self.safety.ph_max:
                violations.append(f"pH ({ph:.2f}) exceeds safety limit ({self.safety.ph_max})")

        if tds is not None:
            if tds < self.safety.tds_min:
                violations.append(f"TDS ({tds:.1f} ppm) below safety limit ({self.safety.tds_min} ppm)")
            elif tds > self.safety.tds_max:
                violations.append(f"TDS ({tds:.1f} ppm) exceeds safety limit ({self.safety.tds_max} ppm)")

        return violations

    def check_normalization_bounds(
        self, temp: Optional[float], ph: Optional[float], tds: Optional[float]
    ) -> List[str]:
        """Check if measurements lie within the expected physical domain bounds for normalization."""
        oob = []
        if temp is not None:
            if temp < self.normalization.temp_min or temp > self.normalization.temp_max:
                oob.append(
                    f"Temperature {temp:.2f}°C outside domain [{self.normalization.temp_min}, {self.normalization.temp_max}]"
                )
        if ph is not None:
            if ph < self.normalization.ph_min or ph > self.normalization.ph_max:
                oob.append(
                    f"pH {ph:.2f} outside domain [{self.normalization.ph_min}, {self.normalization.ph_max}]"
                )
        if tds is not None:
            if tds < self.normalization.tds_min or tds > self.normalization.tds_max:
                oob.append(
                    f"TDS {tds:.1f} ppm outside domain [{self.normalization.tds_min}, {self.normalization.tds_max}]"
                )
        return oob

    def validate_observation(
        self,
        temperature: Optional[float],
        ph: Optional[float],
        tds: Optional[float],
        require_all: bool = False,
    ) -> ValidationResult:
        """Complete validation check for a sensor observation."""
        errors: List[str] = []

        if require_all:
            for name, val in [("temperature", temperature), ("ph", ph), ("tds", tds)]:
                ok, err = self.validate_reading_value(name, val)
                if not ok and err:
                    errors.append(err)
        else:
            # At least one must be valid
            present = [val for val in (temperature, ph, tds) if val is not None]
            if not present:
                errors.append("No sensor values provided in observation")
            for name, val in [("temperature", temperature), ("ph", ph), ("tds", tds)]:
                if val is not None:
                    ok, err = self.validate_reading_value(name, val)
                    if not ok and err:
                        errors.append(err)

        safety_violations = self.check_safety_limits(temperature, ph, tds)
        oob = self.check_normalization_bounds(temperature, ph, tds)

        is_valid = len(errors) == 0
        is_within_bounds = len(oob) == 0
        is_safety = len(safety_violations) > 0

        return ValidationResult(
            is_valid=is_valid,
            is_within_bounds=is_within_bounds,
            is_safety_violation=is_safety,
            errors=errors,
            safety_violations=safety_violations,
            out_of_bounds_fields=oob,
        )
