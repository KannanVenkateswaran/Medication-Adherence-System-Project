import os
from dotenv import load_dotenv
import smtplib
from datetime import datetime, timedelta
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
import json

@dataclass
class MedicationLog:
    timestamp: datetime
    medication_name: str
    dosage_taken: str
    scheduled_time: str
    patient_id: str
    was_taken: bool
    delay_minutes: int = 0

class Patient:
    def __init__(self):
        self.name = ""
        self.id = ""
        self.email = ""
        self.medications = []
        self.emergency_contact = {}
        self.doctor = ""
        self.doctor_email = ""
        self.medication_logs: List[MedicationLog] = []

class MedicationInfo:
    def __init__(self, name: str, dosage_amount: str, dosage_time: str, total_doses: int):
        self.name = name
        self.dosage_amount = dosage_amount
        self.dosage_time = dosage_time
        self.total_doses = total_doses
        self.doses_remaining = total_doses
        self.last_notification_sent = None

class NotificationSystem:
    def __init__(self):
        load_dotenv()
        self.sender_email = "personvcu@gmail.com"
        self.password = os.getenv("EMAIL_PASSWORD")
        self.retry_attempts = 3
        self.retry_delay = 5

    def send_notification(self, patient: Patient, med: MedicationInfo, notification_type: str) -> bool:
        """Send notification with retry mechanism"""
        subject = f"Medication Alert: {med.name}"
        
        if notification_type == "reminder":
            message = (f"Medication Reminder for {patient.name}\n\n"
                      f"Time to take: {med.dosage_time}\n"
                      f"Medication: {med.name}\n"
                      f"Dosage Amount: {med.dosage_amount}\n"
                      f"Doses Remaining: {med.doses_remaining}\n\n"
                      f"Emergency Contact: {patient.emergency_contact['name']} - {patient.emergency_contact['phone']}\n"
                      f"Doctor: {patient.doctor}")
        elif notification_type == "low_dosage":
            message = (f"LOW DOSAGE ALERT for {patient.name}\n\n"
                      f"Medication: {med.name}\n"
                      f"Only {med.doses_remaining} doses remaining!\n\n"
                      f"Please refill your prescription soon or talk to your doctor: {patient.doctor}")
        elif notification_type == "no_dosage":
            message = (f"URGENT: NO DOSES REMAINING for {patient.name}\n\n"
                      f"Medication: {med.name}\n"
                      f"Patient has run out of doses for this medication.\n"
                      f"Please review and provide new prescription if needed.")
        elif notification_type == "missed_dose":
            message = (f"MISSED DOSE ALERT for {patient.name}\n\n"
                      f"Medication: {med.name}\n"
                      f"Scheduled Time: {med.dosage_time}\n"
                      f"You missed your medication. Please take it as soon as possible.")
        elif notification_type == "confirmation_request":
            message = (f"MEDICATION CONFIRMATION REQUEST for {patient.name}\n\n"
                      f"Medication: {med.name}\n"
                      f"Scheduled Time: {med.dosage_time}\n"
                      f"Did you take your medication? Please confirm your status.")
        
        # Send to doctor for missed dose and no dosage scenarios
        if notification_type in ["missed_dose", "no_dosage"] and patient.doctor_email:
            self._send_email(patient.doctor_email, subject, message)
        
        return self._send_email(patient.email, subject, message)

    def send_provider_missed_dose_summary(self, patient: Patient, missed_doses: List[MedicationLog]):
        """Send a summary of missed doses to the provider"""
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

    def _send_email(self, recipient_email: str, subject: str, message: str) -> bool:
        """Helper method to send emails with retry mechanism"""
        for attempt in range(self.retry_attempts):
            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(self.sender_email, self.password)
                
                text = f"Subject: {subject}\n\n{message}"
                server.sendmail(self.sender_email, recipient_email, text)
                print(f"Email sent successfully to {recipient_email}")
                server.quit()
                return True

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                server.quit()

        print(f"WARNING: Failed to deliver notification to {recipient_email} after {self.retry_attempts} attempts")
        return False

class PatientDirectory:
    def __init__(self):
        self.patients = {}
        self.notification_system = NotificationSystem()
        self.log_file = "medication_logs.json"

    def check_missed_doses(self):
        """Check for and handle missed medication doses"""
        current_time = datetime.now()
        for patient_id, patient in self.patients.items():
            for med in patient.medications:
                # Parse the scheduled time
                scheduled_time = datetime.strptime(med.dosage_time, "%I:%M %p").time()
                scheduled_datetime = datetime.combine(current_time.date(), scheduled_time)
                
                # Check if dose is missed (30 minutes after scheduled time)
                missed_threshold = scheduled_datetime + timedelta(minutes=30)
                
                if current_time > missed_threshold:
                    # Check if dose was not logged
                    missed_dose = True
                    for log in patient.medication_logs:
                        if (log.medication_name == med.name and 
                            log.timestamp > scheduled_datetime and 
                            log.timestamp < missed_threshold):
                            missed_dose = False
                            break
                    
                    if missed_dose:
                        # Create missed dose log
                        missed_dose_log = MedicationLog(
                            timestamp=current_time,
                            medication_name=med.name,
                            dosage_taken="",
                            scheduled_time=med.dosage_time,
                            patient_id=patient_id,
                            was_taken=False,
                            delay_minutes=(current_time - scheduled_datetime).total_seconds() / 60
                        )
                        patient.medication_logs.append(missed_dose_log)
                        self._save_log_to_file(missed_dose_log)
                        
                        # Send missed dose and confirmation request notifications
                        self.notification_system.send_notification(patient, med, "missed_dose")
                        self.notification_system.send_notification(patient, med, "confirmation_request")

    def send_weekly_provider_summary(self):
        """Send weekly missed dose summary to providers"""
        for patient_id, patient in self.patients.items():
            # Get missed doses from the past week
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            missed_logs = [
                log for log in patient.medication_logs
                if start_date <= log.timestamp <= end_date and not log.was_taken
            ]
            
            if missed_logs:
                self.notification_system.send_provider_missed_dose_summary(patient, missed_logs)

    def generate_missed_dose_report(self, patient_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Generate a detailed report of missed doses"""
        if patient_id not in self.patients:
            return {"error": "Patient not found"}

        patient = self.patients[patient_id]
        missed_logs = [
            log for log in patient.medication_logs
            if start_date <= log.timestamp <= end_date and not log.was_taken
        ]

        missed_doses_by_medication = {}
        for log in missed_logs:
            if log.medication_name not in missed_doses_by_medication:
                missed_doses_by_medication[log.medication_name] = []
            missed_doses_by_medication[log.medication_name].append(log.timestamp)

        return {
            "patient_name": patient.name,
            "patient_id": patient_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_missed_doses": len(missed_logs),
            "missed_doses": missed_doses_by_medication
        }

    def add_patient(self):
        patient = Patient()
        
        patient.name = input("Enter patient name: ")
        patient.email = input("Enter patient email: ")
        
        while True:
            patient.id = input("Enter patient ID: ")
            if patient.id not in self.patients:
                break
            print("ID already exists. Please enter a unique ID.")

        while True:
            add_med = input("Would you like to add a medication? (yes/no): ").lower()
            if add_med != 'yes':
                break
            med_name = input("Enter medication name: ")
            dosage_amount = input("Enter dosage amount per dose: ")
            dosage_time = input("Enter dosage time (e.g., '8:00 AM, 8:00 PM'): ")
            total_doses = int(input("Enter total number of doses in prescription: "))
            
            med = MedicationInfo(med_name, dosage_amount, dosage_time, total_doses)
            patient.medications.append(med)

        print("\nEmergency Contact Information:")
        contact_name = input("Enter emergency contact name: ")
        contact_phone = input("Enter emergency contact phone: ")
        patient.emergency_contact = {
            "name": contact_name,
            "phone": contact_phone
        }

        patient.doctor = input("Enter doctor's name: ")
        patient.doctor_email = input("Enter doctor's email: ")

        self.patients[patient.id] = patient
        print("\nPatient added successfully!")

    def record_medication_taken(self, patient_id: str, med_index: int):
        """Record that a medication dose was taken and handle notifications"""
        if patient_id not in self.patients:
            print("Patient not found!")
            return

        patient = self.patients[patient_id]
        if med_index >= len(patient.medications):
            print("Invalid medication index!")
            return

        med = patient.medications[med_index]
        current_time = datetime.now()
        
        # Create medication log entry
        log_entry = MedicationLog(
            timestamp=current_time,
            medication_name=med.name,
            dosage_taken=med.dosage_amount,
            scheduled_time=med.dosage_time,
            patient_id=patient_id,
            was_taken=True
        )
        
        # Add log to patient's records
        patient.medication_logs.append(log_entry)
        
        # Save log to file
        self._save_log_to_file(log_entry)
        
        if med.doses_remaining > 0:
            med.doses_remaining -= 1
            print(f"Recorded dose taken. {med.doses_remaining} doses remaining.")

            self.notification_system.send_notification(patient, med, "reminder")

            if med.doses_remaining == 5:
                if not self.notification_system.send_notification(patient, med, "low_dosage"):
                    print("WARNING: Failed to send low dosage alert!")

            if med.doses_remaining == 0:
                if not self.notification_system.send_notification(patient, med, "no_dosage"):
                    print("WARNING: Failed to send no dosage alert!")
        else:
            print("No doses remaining! Please refill prescription.")

    def _save_log_to_file(self, log: MedicationLog):
        """Save medication log to JSON file"""
        log_dict = {
            "timestamp": log.timestamp.isoformat(),
            "medication_name": log.medication_name,
            "dosage_taken": log.dosage_taken,
            "scheduled_time": log.scheduled_time,
            "patient_id": log.patient_id,
            "was_taken": log.was_taken,
            "delay_minutes": log.delay_minutes
        }
        
        try:
            with open(self.log_file, 'a') as f:
                json.dump(log_dict, f)
                f.write('\n')
        except Exception as e:
            print(f"Error saving log: {e}")

    def generate_adherence_report(self, patient_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Generate medication adherence report for a specific time period"""
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

        medication_breakdown = {}
        for log in relevant_logs:
            if log.medication_name not in medication_breakdown:
                medication_breakdown[log.medication_name] = {
                    "doses_taken": 0,
                    "total_doses": 0
                }
            medication_breakdown[log.medication_name]["total_doses"] += 1
            if log.was_taken:
                medication_breakdown[log.medication_name]["doses_taken"] += 1

        return {
            "patient_name": patient.name,
            "patient_id": patient_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "overall_adherence_rate": adherence_rate,
            "total_doses": total_doses,
            "doses_taken": doses_taken,
            "medication_breakdown": medication_breakdown
        }
    def display_patient(self, patient_id):
        if patient_id in self.patients:
            patient = self.patients[patient_id]
            print("\nPatient Information:")
            print(f"Name: {patient.name}")
            print(f"ID: {patient.id}")
            print(f"Email: {patient.email}")
            print("\nMedications:")
            if patient.medications:
                for i, med in enumerate(patient.medications):
                    print(f"{i+1}. {med.name}")
                    print(f"   Dosage: {med.dosage_amount}")
                    print(f"   Time: {med.dosage_time}")
                    print(f"   Doses Remaining: {med.doses_remaining}")
            else:
                print("No medications listed")
            print(f"\nEmergency Contact: {patient.emergency_contact['name']}")
            print(f"Emergency Phone: {patient.emergency_contact['phone']}")
            print(f"Doctor: {patient.doctor}")
            print(f"Doctor Email: {patient.doctor_email}")
        else:
            print("Patient not found!")

    def run(self):
            while True:
                print("\nPatient Directory Menu:")
                print("1. Add new patient")
                print("2. Display patient information")
                print("3. Record medication taken")
                print("4. Generate adherence report")
                print("5. Exit")
                
                choice = input("\nEnter your choice (1-5): ")
                
                if choice == "1":
                    self.add_patient()
                elif choice == "2":
                    patient_id = input("Enter patient ID to display: ")
                    self.display_patient(patient_id)
                elif choice == "3":
                    patient_id = input("Enter patient ID: ")
                    if patient_id in self.patients:
                        self.display_patient(patient_id)
                        med_index = int(input("Enter medication number to record: ")) - 1
                        self.record_medication_taken(patient_id, med_index)
                    else:
                        print("Patient not found!")
                elif choice == "4":
                    patient_id = input("Enter patient ID: ")
                    days = int(input("Enter number of days for report period: "))
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=days)
                    report = self.generate_adherence_report(patient_id, start_date, end_date)
                    print("\nAdherence Report:")
                    print(json.dumps(report, indent=2))
                elif choice == "5":
                    print("Exiting program...")
                    break
                else:
                    print("Invalid choice. Please try again.")

if __name__ == "__main__":
    directory = PatientDirectory()
    directory.run()