from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


"""
Data model definitions for the medication adherence class project.

This module contains the small dataclasses used throughout the program:
- `MedicationLog` records a single taken or missed dose.
- `Patient` stores the main patient information and their logs.
- `MedicationInfo` describes the medication name, dosage, and schedule.

The types are intentionally simple so they are easy to understand in class and
easy to use in tests.
"""


@dataclass
class MedicationLog:
    """
    A single log entry for a medication event.

    Attributes:
        timestamp: When the event was recorded.
        medication_name: The name/identifier of the medication.
        dosage_taken: Human-readable dosage taken (empty for missed doses).
        scheduled_time: The scheduled time text (e.g., "8:00 AM").
        patient_id: The id of the patient this log belongs to.
        was_taken: True when the dose was recorded as taken, False when missed.
        delay_minutes: If missed, how many minutes after scheduled time it was recorded.
    """
    timestamp: datetime
    medication_name: str
    dosage_taken: str
    scheduled_time: str
    patient_id: str
    was_taken: bool
    delay_minutes: int = 0


@dataclass
class Patient:
    """
    Represents a patient and their medication-related state.

    Fields are public and simple so tests and scripts can construct `Patient`
    instances easily. `medication_logs` stores `MedicationLog` entries in
    chronological order as they are recorded.
    """
    name: str = ""
    id: str = ""
    email: str = ""
    medications: List["MedicationInfo"] = field(default_factory=list)
    emergency_contact: Dict[str, str] = field(default_factory=dict)
    doctor: str = ""
    doctor_email: str = ""
    medication_logs: List[MedicationLog] = field(default_factory=list)


@dataclass
class MedicationInfo:
    """
    Information about a prescribed medication.

    Notes:
      - `dosage_times` is a list of textual times (e.g. ["8:00 AM", "8:00 PM"]).
        This representation keeps parsing/formatting in one place and lets the
        rest of the system treat schedules as simple strings.
      - `doses_remaining` is initialized from `total_doses` in `__post_init__`.
    """
    name: str
    dosage_amount: str
    dosage_times: List[str]
    total_doses: int
    doses_remaining: int = field(init=False)
    last_notification_sent: Optional[datetime] = None

    def __post_init__(self) -> None:
        # Clean the incoming dosage time values so the rest of the program can
        # work with a predictable list.
        cleaned_times = [time.strip() for time in self.dosage_times if time and time.strip()]
        self.dosage_times = cleaned_times if cleaned_times else [""]

        # Start the remaining dose count from the total prescribed count.
        self.doses_remaining = self.total_doses

    @property
    def dosage_time(self) -> str:
        """
        Return a human readable representation of scheduled times.

        Examples: "8:00 AM" or "8:00 AM, 8:00 PM".
        """
        return ", ".join([time for time in self.dosage_times if time]).strip()
