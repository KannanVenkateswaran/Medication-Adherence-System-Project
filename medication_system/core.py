from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from .models import MedicationInfo, MedicationLog, Patient
from .notifications import NotificationSystem


"""
Core logic for the medication adherence class project.

This module implements the `PatientDirectory`, which stores the in-memory
patient records used by the program and provides the main operations for
recording doses, checking missed doses, and producing short reports.
"""


def parse_dosage_times(raw_times: str | Sequence[str]) -> List[str]:
    """
    Parse a comma-separated string or sequence of time-like values.

    The function returns a cleaned list of textual times (for example,
    ["8:00 AM", "8:00 PM"]). When no usable value is provided, it returns
    a single empty string so the rest of the program can keep the same
    simple control flow.
    """
    if isinstance(raw_times, str):
        parts = [part.strip() for part in raw_times.split(",")]
    else:
        parts = [str(part).strip() for part in raw_times]

    cleaned = [part for part in parts if part]
    return cleaned if cleaned else [""]


class PatientDirectory:
    """
    Registry and rules for the patient records used by the project.

    The class keeps track of patients during program execution and provides
    the operations needed by the assignment: recording doses, checking for
    missed doses, and generating simple report data.

    Time-related behaviour is driven by a `clock` callable so tests can use a
    fixed time and produce repeatable results.
    """

    def __init__(
        self,
        notification_system: Optional[NotificationSystem] = None,
        clock: Callable[[], datetime] = datetime.now,
        log_file: str = "medication_logs.json",
    ) -> None:
        # Map patient id -> Patient record.
        self.patients: Dict[str, Patient] = {}
        self.notification_system = notification_system or NotificationSystem()
        # `clock` returns the current datetime and can be replaced in tests.
        self.clock = clock
        self.log_file = log_file

    def add_patient(self, patient: Patient) -> None:
        """
        Add a new patient to the directory.

        Raises ValueError for missing or duplicate ids.
        """
        if not patient.id:
            raise ValueError("Patient ID is required")
        if patient.id in self.patients:
            raise ValueError("Patient ID already exists")
        self.patients[patient.id] = patient

    def check_missed_doses(self) -> None:
        """
        Scan all patients and create logs for doses that appear missed.

        For each scheduled time, the program computes the corresponding time on
        the current day and applies a 30-minute grace period. If the current
        time is past that window and no taken dose was logged, a missed-dose
        record is added and the notification flow is triggered.
        """
        current_time = self.clock()

        for patient_id, patient in self.patients.items():
            for med in patient.medications:
                for scheduled_time_text in med.dosage_times:
                    if not scheduled_time_text:
                        continue

                    try:
                        scheduled_datetime = self._scheduled_datetime(current_time, scheduled_time_text)
                    except ValueError as exc:
                        # Skip badly formatted times instead of stopping the scan.
                        print(f"Warning: skipping scheduled time '{scheduled_time_text}': {exc}")
                        continue

                    missed_threshold = scheduled_datetime + timedelta(minutes=30)

                    # Still inside the grace period, so do not mark it missed yet.
                    if current_time <= missed_threshold:
                        continue

                    # If a taken log already exists for this window, do nothing.
                    if self._has_taken_dose(patient, med.name, scheduled_time_text, scheduled_datetime, missed_threshold):
                        continue

                    missed_dose_log = MedicationLog(
                        timestamp=current_time,
                        medication_name=med.name,
                        dosage_taken="",
                        scheduled_time=scheduled_time_text,
                        patient_id=patient_id,
                        was_taken=False,
                        delay_minutes=int((current_time - scheduled_datetime).total_seconds() // 60),
                    )
                    patient.medication_logs.append(missed_dose_log)
                    self._save_log_to_file(missed_dose_log)

                    # Notify the patient and request confirmation for the missed dose.
                    self.notification_system.send_notification(patient, med, "missed_dose")
                    self.notification_system.send_notification(patient, med, "confirmation_request")

    def send_weekly_provider_summary(self) -> None:
        """
        Build and send a summary of missed doses for the past 7 days.

        Any patient with missed doses in the time window will trigger a summary
        message to the listed provider email.
        """
        end_date = self.clock()
        start_date = end_date - timedelta(days=7)

        for patient in self.patients.values():
            missed_logs = [
                log for log in patient.medication_logs
                if start_date <= log.timestamp <= end_date and not log.was_taken
            ]

            if missed_logs:
                self.notification_system.send_provider_missed_dose_summary(patient, missed_logs)

    def generate_missed_dose_report(self, patient_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """
        Return a missed-dose report for a patient over a date range.

        The returned structure is kept plain so it can be printed, inspected,
        or serialized to JSON without extra processing.
        """
        if patient_id not in self.patients:
            return {"error": "Patient not found"}

        patient = self.patients[patient_id]
        missed_logs = [
            log for log in patient.medication_logs
            if start_date <= log.timestamp <= end_date and not log.was_taken
        ]

        missed_doses_by_medication: Dict[str, List[datetime]] = {}
        for log in missed_logs:
            missed_doses_by_medication.setdefault(log.medication_name, []).append(log.timestamp)

        return {
            "patient_name": patient.name,
            "patient_id": patient_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_missed_doses": len(missed_logs),
            "missed_doses": missed_doses_by_medication,
        }

    def record_medication_taken(
        self,
        patient_id: str,
        med_index: int,
        scheduled_time: Optional[str] = None,
    ) -> None:
        """
        Record that a patient has taken a medication dose.

        The method adds a `MedicationLog`, writes it to the log file, and
        decreases the remaining dose count for the medication.
        """
        if patient_id not in self.patients:
            print("Patient not found!")
            return

        patient = self.patients[patient_id]
        if med_index < 0 or med_index >= len(patient.medications):
            print("Invalid medication index!")
            return

        med = patient.medications[med_index]
        current_time = self.clock()
        scheduled_time_text = scheduled_time or self._select_scheduled_time(patient, med)

        log_entry = MedicationLog(
            timestamp=current_time,
            medication_name=med.name,
            dosage_taken=med.dosage_amount,
            scheduled_time=scheduled_time_text,
            patient_id=patient_id,
            was_taken=True,
        )
        patient.medication_logs.append(log_entry)
        self._save_log_to_file(log_entry)

        if med.doses_remaining > 0:
            med.doses_remaining -= 1
            print(f"Recorded dose taken. {med.doses_remaining} doses remaining.")

            # Notify the user when the prescription is nearly finished.
            if med.doses_remaining == 5:
                if not self.notification_system.send_notification(patient, med, "low_dosage"):
                    print("WARNING: Failed to send low dosage alert!")

            if med.doses_remaining == 0:
                if not self.notification_system.send_notification(patient, med, "no_dosage"):
                    print("WARNING: Failed to send no dosage alert!")
        else:
            print("No doses remaining! Please refill prescription.")

    def generate_adherence_report(self, patient_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """
        Create a concise adherence report for the given date range.

        The function computes an overall adherence percentage and a simple
        per-medication breakdown of doses taken versus total logged doses.
        """
        if patient_id not in self.patients:
            return {"error": "Patient not found"}

        patient = self.patients[patient_id]
        relevant_logs = [
            log for log in patient.medication_logs
            if start_date <= log.timestamp <= end_date
        ]

        total_doses = len(relevant_logs)
        doses_taken = len([log for log in relevant_logs if log.was_taken])
        adherence_rate = (doses_taken / total_doses * 100) if total_doses > 0 else 0

        medication_breakdown: Dict[str, Dict[str, int]] = {}
        for log in relevant_logs:
            medication_breakdown.setdefault(log.medication_name, {"doses_taken": 0, "total_doses": 0})
            medication_breakdown[log.medication_name]["total_doses"] += 1
            if log.was_taken:
                medication_breakdown[log.medication_name]["doses_taken"] += 1

        return {
            "patient_name": patient.name,
            "patient_id": patient_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "overall_adherence_rate": adherence_rate,
            "total_doses": total_doses,
            "doses_taken": doses_taken,
            "medication_breakdown": medication_breakdown,
        }

    def display_patient(self, patient_id: str) -> None:
        """
        Print a human readable summary of a patient's details to stdout.

        This helper is used by the CLI during manual runs of the program.
        """
        if patient_id in self.patients:
            patient = self.patients[patient_id]
            print("\nPatient Information:")
            print(f"Name: {patient.name}")
            print(f"ID: {patient.id}")
            print(f"Email: {patient.email}")
            print("\nMedications:")
            if patient.medications:
                for i, med in enumerate(patient.medications):
                    print(f"{i + 1}. {med.name}")
                    print(f"   Dosage: {med.dosage_amount}")
                    print(f"   Time: {med.dosage_time}")
                    print(f"   Doses Remaining: {med.doses_remaining}")
            else:
                print("No medications listed")
            print(f"\nEmergency Contact: {patient.emergency_contact.get('name', '')}")
            print(f"Emergency Phone: {patient.emergency_contact.get('phone', '')}")
            print(f"Doctor: {patient.doctor}")
            print(f"Doctor Email: {patient.doctor_email}")
        else:
            print("Patient not found!")

    def _scheduled_datetime(self, current_time: datetime, scheduled_time_text: str) -> datetime:
        """
        Parse a textual scheduled time and return a datetime for today.

        The parser accepts a few common formats so the project is easier to use
        during demonstrations and class testing. It also removes surrounding
        quotes and extra whitespace before parsing.
        """
        # Remove accidental surrounding quotes and whitespace.
        s = scheduled_time_text.strip().strip('"').strip("'")

        # Try several reasonable formats.
        tried_formats = ["%I:%M %p", "%I:%M%p", "%H:%M"]
        last_exc: Optional[Exception] = None
        for fmt in tried_formats:
            try:
                parsed_time = datetime.strptime(s.upper(), fmt).time()
                return datetime.combine(current_time.date(), parsed_time)
            except Exception as exc:  # ValueError or similar
                last_exc = exc

        # If parsing failed for all formats, raise a clear error for the caller.
        raise ValueError(f"Unable to parse scheduled time '{scheduled_time_text}': {last_exc}")

    def _has_taken_dose(
        self,
        patient: Patient,
        medication_name: str,
        scheduled_time_text: str,
        scheduled_datetime: datetime,
        missed_threshold: datetime,
    ) -> bool:
        """
        Return True if a taken log exists for the medication and time window.

        The check looks for logs recorded between `scheduled_datetime` and
        `missed_threshold` and matches on medication name and scheduled time.
        """
        return any(
            log.medication_name == medication_name
            and log.scheduled_time == scheduled_time_text
            and log.was_taken
            and scheduled_datetime <= log.timestamp <= missed_threshold
            for log in patient.medication_logs
        )

    def _select_scheduled_time(self, patient: Patient, med: MedicationInfo) -> str:
        """
        Choose which scheduled time to attribute a recorded dose to.

        The method returns the first scheduled time that does not already have a
        taken log for the same medication on the current day.
        """
        for scheduled_time_text in med.dosage_times:
            if not scheduled_time_text:
                continue
            if not any(
                log.medication_name == med.name and log.scheduled_time == scheduled_time_text and log.was_taken
                for log in patient.medication_logs
            ):
                return scheduled_time_text
        return med.dosage_times[0] if med.dosage_times else ""

    def _save_log_to_file(self, log: MedicationLog) -> None:
        """
        Append a JSON-lines representation of `log` to the configured log file.

        Errors are printed instead of raised so the interactive program can keep
        running during class demonstrations.
        """
        log_dict = {
            "timestamp": log.timestamp.isoformat(),
            "medication_name": log.medication_name,
            "dosage_taken": log.dosage_taken,
            "scheduled_time": log.scheduled_time,
            "patient_id": log.patient_id,
            "was_taken": log.was_taken,
            "delay_minutes": log.delay_minutes,
        }

        try:
            log_path = Path(self.log_file)
            with log_path.open("a", encoding="utf-8") as file_handle:
                json.dump(log_dict, file_handle)
                file_handle.write("\n")
        except Exception as exc:
            print(f"Error saving log: {exc}")
