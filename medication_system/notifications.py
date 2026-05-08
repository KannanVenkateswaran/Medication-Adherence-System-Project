from __future__ import annotations

import os
import smtplib
import time
from typing import Callable, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv() -> None:
        return None

from .models import MedicationInfo, MedicationLog, Patient


"""
Notification helpers for the medication adherence class project.

This module wraps email notification behaviour behind a small
`NotificationSystem` class. The implementation accepts an `smtp_factory` and
`sleep_fn` so the code can be tested without sending real email.
"""


class NotificationSystem:
    """
    Sends notifications to patients and providers.

    The class builds short text messages and delivers them by email. For
    testing, callers may supply a custom `smtp_factory` that returns an object
    with `starttls`, `login`, `sendmail`, and `quit` methods.
    """
    def __init__(
        self,
        sender_email: str = "personvcu@gmail.com",
        password: Optional[str] = None,
        smtp_factory: Callable[[str, int], smtplib.SMTP] = smtplib.SMTP,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        # Load environment variables if a `.env` file is present.
        load_dotenv()
        self.sender_email = sender_email
        self.password = password if password is not None else os.getenv("EMAIL_PASSWORD")
        self.smtp_factory = smtp_factory
        self.sleep_fn = sleep_fn
        # Retry settings for temporary SMTP failures.
        self.retry_attempts = 3
        self.retry_delay = 5

    def send_notification(self, patient: Patient, med: MedicationInfo, notification_type: str) -> bool:
        """
        Send a single notification to a patient, and sometimes a provider.

        Returns True when delivery to the patient succeeds, False otherwise.
        Certain notification types also notify the patient's doctor when an
        email address is available.
        """
        subject, message = self._build_message(patient, med, notification_type)

        # For more important alerts, notify the provider first when possible.
        if notification_type in ["missed_dose", "no_dosage"] and patient.doctor_email:
            self._send_email(patient.doctor_email, subject, message)

        return self._send_email(patient.email, subject, message)

    def send_provider_missed_dose_summary(self, patient: Patient, missed_doses: List[MedicationLog]) -> bool:
        """
        Send a summary to the provider with missed-dose details.

        Returns False immediately when no provider email is available.
        """
        if not patient.doctor_email:
            print("No provider email found")
            return False

        subject = f"Missed Medication Doses Summary for {patient.name}"
        message = "Missed Medication Doses Summary:\n\n"

        for dose in missed_doses:
            message += f"Medication: {dose.medication_name}\n"
            message += f"Scheduled Time: {dose.scheduled_time}\n"
            message += f"Missed at: {dose.timestamp}\n\n"

        return self._send_email(patient.doctor_email, subject, message)

    def _build_message(self, patient: Patient, med: MedicationInfo, notification_type: str) -> tuple[str, str]:
        """
        Create subject and message text for supported notification types.

        Keeping message generation in one place makes the code easier to read
        and easier to update if the text needs to change.
        """
        subject = f"Medication Alert: {med.name}"

        if notification_type == "reminder":
            message = (
                f"Medication Reminder for {patient.name}\n\n"
                f"Time to take: {med.dosage_time}\n"
                f"Medication: {med.name}\n"
                f"Dosage Amount: {med.dosage_amount}\n"
                f"Doses Remaining: {med.doses_remaining}\n\n"
                f"Emergency Contact: {patient.emergency_contact.get('name', '')} - {patient.emergency_contact.get('phone', '')}\n"
                f"Doctor: {patient.doctor}"
            )
        elif notification_type == "low_dosage":
            message = (
                f"LOW DOSAGE ALERT for {patient.name}\n\n"
                f"Medication: {med.name}\n"
                f"Only {med.doses_remaining} doses remaining!\n\n"
                f"Please refill your prescription soon or talk to your doctor: {patient.doctor}"
            )
        elif notification_type == "no_dosage":
            message = (
                f"URGENT: NO DOSES REMAINING for {patient.name}\n\n"
                f"Medication: {med.name}\n"
                f"Patient has run out of doses for this medication.\n"
                f"Please review and provide new prescription if needed."
            )
        elif notification_type == "missed_dose":
            message = (
                f"MISSED DOSE ALERT for {patient.name}\n\n"
                f"Medication: {med.name}\n"
                f"Scheduled Time: {med.dosage_time}\n"
                f"You missed your medication. Please take it as soon as possible."
            )
        elif notification_type == "confirmation_request":
            message = (
                f"MEDICATION CONFIRMATION REQUEST for {patient.name}\n\n"
                f"Medication: {med.name}\n"
                f"Scheduled Time: {med.dosage_time}\n"
                f"Did you take your medication? Please confirm your status."
            )
        else:
            raise ValueError(f"Unsupported notification type: {notification_type}")

        return subject, message

    def _send_email(self, recipient_email: str, subject: str, message: str) -> bool:
        """
        Deliver a plain-text email via the configured SMTP factory.

        The method retries on temporary failures and uses the injected
        `sleep_fn` between attempts so tests do not need to pause in real time.
        """
        for attempt in range(self.retry_attempts):
            server = None
            try:
                server = self.smtp_factory("smtp.gmail.com", 587)
                server.starttls()
                server.login(self.sender_email, self.password)

                text = f"Subject: {subject}\n\n{message}"
                server.sendmail(self.sender_email, recipient_email, text)
                print(f"Email sent successfully to {recipient_email}")
                return True
            except Exception as exc:
                print(f"Attempt {attempt + 1} failed: {exc}")
                if attempt < self.retry_attempts - 1:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    self.sleep_fn(self.retry_delay)
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

        print(f"WARNING: Failed to deliver notification to {recipient_email} after {self.retry_attempts} attempts")
        return False