"""
sensor_models.py — Strongly typed sensor data model using Pydantic.

Represents one snapshot from the wearable device.
Derived values (acceleration_magnitude, etc.) are computed automatically.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field, model_validator, ConfigDict


class SensorReading(BaseModel):
    """
    One timestamped snapshot of all sensor channels from the wearable.
    All raw fields represent physical values in SI / common units.
    """

    # -----------------------------------------------------------------------
    # Identity / Timing
    # -----------------------------------------------------------------------
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reading_id: Optional[str] = None

    # -----------------------------------------------------------------------
    # Biometric sensors
    # -----------------------------------------------------------------------
    heart_rate: Optional[float] = Field(None, description="Heart rate in bpm")
    spo2: Optional[float] = Field(None, description="Peripheral oxygen saturation %")
    body_temperature: Optional[float] = Field(None, description="Wrist skin temperature °C")

    # -----------------------------------------------------------------------
    # Environmental sensors
    # -----------------------------------------------------------------------
    environment_temperature: Optional[float] = Field(None, description="Ambient temperature °C")
    humidity: Optional[float] = Field(None, description="Relative humidity %")
    altitude: Optional[float] = Field(None, description="Altitude above sea level in metres")
    atmospheric_pressure: Optional[float] = Field(None, description="Atmospheric pressure in hPa")

    # -----------------------------------------------------------------------
    # Motion sensors (accelerometer in g-units)
    # -----------------------------------------------------------------------
    acceleration_x: Optional[float] = Field(None, description="Acceleration X-axis g")
    acceleration_y: Optional[float] = Field(None, description="Acceleration Y-axis g")
    acceleration_z: Optional[float] = Field(None, description="Acceleration Z-axis g")

    # -----------------------------------------------------------------------
    # Pre-classified fields (populated by upstream stages)
    # -----------------------------------------------------------------------
    activity_state: Optional[str] = Field(None, description="Classified activity state")

    # -----------------------------------------------------------------------
    # Previous reading reference (for delta calculations)
    # -----------------------------------------------------------------------
    previous_altitude: Optional[float] = Field(None, description="Previous altitude for Δ calculation")
    previous_pressure: Optional[float] = Field(None, description="Previous pressure for Δ calculation")

    # -----------------------------------------------------------------------
    # Derived / computed fields
    # -----------------------------------------------------------------------
    @computed_field
    @property
    def acceleration_magnitude(self) -> Optional[float]:
        """Euclidean magnitude of acceleration vector in g-units."""
        if (
            self.acceleration_x is not None
            and self.acceleration_y is not None
            and self.acceleration_z is not None
        ):
            return round(
                math.sqrt(
                    self.acceleration_x ** 2
                    + self.acceleration_y ** 2
                    + self.acceleration_z ** 2
                ),
                3,
            )
        return None

    @computed_field
    @property
    def altitude_change(self) -> Optional[float]:
        """Change in altitude since previous reading (metres)."""
        if self.altitude is not None and self.previous_altitude is not None:
            return round(self.altitude - self.previous_altitude, 1)
        return None

    @computed_field
    @property
    def pressure_change(self) -> Optional[float]:
        """Change in atmospheric pressure since previous reading (hPa)."""
        if (
            self.atmospheric_pressure is not None
            and self.previous_pressure is not None
        ):
            return round(self.atmospheric_pressure - self.previous_pressure, 2)
        return None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SensorReadingSequence(BaseModel):
    """
    A named sequence of sensor readings representing one scenario.
    """

    scenario_id: int
    scenario_name: str
    description: str
    readings: list[SensorReading]
    expected_outcome: str
