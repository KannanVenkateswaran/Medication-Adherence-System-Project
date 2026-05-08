from __future__ import annotations

import json
from datetime import datetime, timedelta

from .core import PatientDirectory, parse_dosage_times
from .models import MedicationInfo, Patient


"""
Simple interactive command-line interface for the medication system.

This module provides two functions:
- `prompt_patient()` which interactively gathers patient data from stdin
- `main()` which runs a small menu loop for ad-hoc manual testing

The CLI is intentionally very small to match scope of projected completed during CMSC 355.
"""


def prompt_patient() -> Patient:
    """
    Interactively prompt the user for patient and medication details.

    Returns a fully populated `Patient` instance ready to be added to the
    `PatientDirectory`.
    """
    patient = Patient()

    patient.name = input("Enter patient name: ")
    patient.email = input("Enter patient email: ")
    patient.id = input("Enter patient ID: ")

    while True:
        add_medication = input("Would you like to add a medication? (yes/no): ").strip().lower()
        if add_medication != "yes":
            break

        med_name = input("Enter medication name: ")
        dosage_amount = input("Enter dosage amount per dose: ")
        dosage_times = parse_dosage_times(
            input("Enter dosage time(s), comma-separated if needed (e.g., '8:00 AM, 8:00 PM'): ")
        )
        total_doses = int(input("Enter total number of doses in prescription: "))

        patient.medications.append(MedicationInfo(med_name, dosage_amount, dosage_times, total_doses))

    print("\nEmergency Contact Information:")
    contact_name = input("Enter emergency contact name: ")
    contact_phone = input("Enter emergency contact phone: ")
    patient.emergency_contact = {"name": contact_name, "phone": contact_phone}

    patient.doctor = input("Enter doctor's name: ")
    patient.doctor_email = input("Enter doctor's email: ")

    return patient


def main() -> None:
    """
    Run a small interactive menu to exercise the `PatientDirectory`.

    The function is deliberately simple and intended for manual testing rather
    than automated usage. For programmatic interactions use `PatientDirectory`
    directly from scripts or tests.
    """
    directory = PatientDirectory()

    while True:
        print("\nPatient Directory Menu:")
        print("1. Add new patient")
        print("2. Display patient information")
        print("3. Record medication taken")
        print("4. Generate adherence report")
        print("5. Check missed doses")
        print("6. Exit")

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            try:
                patient = prompt_patient()
                directory.add_patient(patient)
                print("\nPatient added successfully!")
            except ValueError as exc:
                print(exc)
        elif choice == "2":
            patient_id = input("Enter patient ID to display: ")
            directory.display_patient(patient_id)
        elif choice == "3":
            patient_id = input("Enter patient ID: ")
            if patient_id in directory.patients:
                directory.display_patient(patient_id)
                med_index = int(input("Enter medication number to record: ")) - 1
                directory.record_medication_taken(patient_id, med_index)
            else:
                print("Patient not found!")
        elif choice == "4":
            patient_id = input("Enter patient ID: ")
            days = int(input("Enter number of days for report period: "))
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            report = directory.generate_adherence_report(patient_id, start_date, end_date)
            print("\nAdherence Report:")
            print(json.dumps(report, indent=2, default=str))
        elif choice == "5":
            directory.check_missed_doses()
            print("Missed dose check complete.")
        elif choice == "6":
            print("Exiting program...")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()