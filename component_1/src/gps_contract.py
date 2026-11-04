"""Minimal source-agnostic GPS observation contract for Component 1.

The downstream GNN pipeline must consume only these fields, regardless of
whether observations come from this simulator, a phone, or an onboard GPS.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Protocol, TypedDict, Iterable
import math


class GPSObservation(TypedDict):
    device_id: str
    timestamp: str
    latitude: float
    longitude: float


GPS_FIELDS = ("device_id", "timestamp", "latitude", "longitude")


class GPSObservationSource(Protocol):
    """Any real or simulated source that streams GPS observations."""
    def stream(self, duration_s: float) -> Iterable[tuple[float, list[GPSObservation]]]: ...


def validate_observation(record: Mapping) -> GPSObservation:
    """Validate and return the exact public GPS schema; reject simulator internals."""
    keys = tuple(record.keys())
    if set(keys) != set(GPS_FIELDS):
        missing = sorted(set(GPS_FIELDS) - set(keys))
        extra = sorted(set(keys) - set(GPS_FIELDS))
        raise ValueError(f"GPS schema mismatch; missing={missing}, extra={extra}")
    if not isinstance(record["device_id"], str) or not record["device_id"].strip():
        raise ValueError("device_id must be a non-empty pseudonymous string")
    datetime.fromisoformat(str(record["timestamp"]))
    lat, lon = float(record["latitude"]), float(record["longitude"])
    if not (math.isfinite(lat) and -90 <= lat <= 90):
        raise ValueError("latitude must be finite and between -90 and 90")
    if not (math.isfinite(lon) and -180 <= lon <= 180):
        raise ValueError("longitude must be finite and between -180 and 180")
    return {
        "device_id": record["device_id"],
        "timestamp": str(record["timestamp"]),
        "latitude": lat,
        "longitude": lon,
    }
