from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
import unittest

from medication_system.core import PatientDirectory, parse_dosage_times
from medication_system.models import MedicationInfo, MedicationLog, Patient


class FakeNotificationSystem:
    def __init__(self) -> None:
        self.calls = []

    def send_notification(self, patient, med, notification_type):
        self.calls.append((patient.id, med.name, notification_type))
        return True

    def send_provider_missed_dose_summary(self, patient, missed_doses):
        self.calls.append((patient.id, "summary", len(missed_doses)))
        return True


class FixedClock:
    def __init__(self, fixed_time: datetime) -> None:
        self.fixed_time = fixed_time

    def __call__(self) -> datetime:
        return self.fixed_time


class PatientDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.log_file = str(Path(self.temp_dir.name) / "logs.jsonl")

    def test_parse_dosage_times_handles_multiple_values(self) -> None:
        self.assertEqual(parse_dosage_times("8:00 AM, 8:00 PM"), ["8:00 AM", "8:00 PM"])

    def test_record_medication_taken_updates_state_and_sends_low_dosage_alert(self) -> None:
        fake_notifications = FakeNotificationSystem()
        directory = PatientDirectory(
            notification_system=fake_notifications,
            clock=FixedClock(datetime(2026, 5, 7, 8, 0)),
            log_file=self.log_file,
        )

        patient = Patient(
            name="Alex",
            id="P1",
            email="alex@example.com",
            medications=[MedicationInfo("MedA", "1 tablet", ["8:00 AM"], 6)],
            emergency_contact={"name": "Sam", "phone": "555-0100"},
            doctor="Dr. Lee",
            doctor_email="doctor@example.com",
        )
        directory.add_patient(patient)

        directory.record_medication_taken("P1", 0)

        self.assertEqual(patient.medications[0].doses_remaining, 5)
        self.assertEqual(len(patient.medication_logs), 1)
        self.assertEqual(fake_notifications.calls[-1], ("P1", "MedA", "low_dosage"))

        with open(self.log_file, "r", encoding="utf-8") as file_handle:
            saved_log = json.loads(file_handle.readline())

        self.assertTrue(saved_log["was_taken"])
        self.assertEqual(saved_log["scheduled_time"], "8:00 AM")

    def test_check_missed_doses_creates_missed_log_and_notifications(self) -> None:
        fake_notifications = FakeNotificationSystem()
        directory = PatientDirectory(
            notification_system=fake_notifications,
            clock=FixedClock(datetime(2026, 5, 7, 9, 45)),
            log_file=self.log_file,
        )

        patient = Patient(
            name="Alex",
            id="P2",
            email="alex@example.com",
            medications=[MedicationInfo("MedB", "1 tablet", ["8:00 AM"], 10)],
            emergency_contact={"name": "Sam", "phone": "555-0100"},
            doctor="Dr. Lee",
            doctor_email="doctor@example.com",
        )
        directory.add_patient(patient)

        directory.check_missed_doses()

        self.assertEqual(len(patient.medication_logs), 1)
        self.assertFalse(patient.medication_logs[0].was_taken)
        self.assertEqual(
            fake_notifications.calls,
            [("P2", "MedB", "missed_dose"), ("P2", "MedB", "confirmation_request")],
        )

    def test_generate_adherence_report_counts_taken_and_missed_logs(self) -> None:
        directory = PatientDirectory(
            notification_system=FakeNotificationSystem(),
            clock=FixedClock(datetime(2026, 5, 7, 12, 0)),
            log_file=self.log_file,
        )

        patient = Patient(
            name="Alex",
            id="P3",
            email="alex@example.com",
            medications=[MedicationInfo("MedC", "1 tablet", ["8:00 AM"], 10)],
            emergency_contact={"name": "Sam", "phone": "555-0100"},
            doctor="Dr. Lee",
            doctor_email="doctor@example.com",
        )
        directory.add_patient(patient)

        patient.medication_logs.extend(
            [
                MedicationLog(
                    timestamp=datetime(2026, 5, 7, 8, 0),
                    medication_name="MedC",
                    dosage_taken="1 tablet",
                    scheduled_time="8:00 AM",
                    patient_id="P3",
                    was_taken=True,
                ),
                MedicationLog(
                    timestamp=datetime(2026, 5, 7, 8, 45),
                    medication_name="MedC",
                    dosage_taken="",
                    scheduled_time="8:00 AM",
                    patient_id="P3",
                    was_taken=False,
                ),
            ]
        )

        report = directory.generate_adherence_report("P3", datetime(2026, 5, 7, 0, 0), datetime(2026, 5, 7, 23, 59))

        self.assertEqual(report["total_doses"], 2)
        self.assertEqual(report["doses_taken"], 1)
        self.assertEqual(report["overall_adherence_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
