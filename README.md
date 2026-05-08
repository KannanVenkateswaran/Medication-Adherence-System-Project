# Medication Adherence System - Fundmentals of Software Engineering (CMSC 355)

**Group Members:** Mezmure Dawit, Kiet Hyunh, Christopher Lee, Syed Ibad Rahman, Ayush Upadhyay, Kannan Venkateswaran

**Iteration 1 Completion:** 12/05/2026 - Completed by Group
**Iteration 2 Completion:** 05/08/2026 - Completed by Kannan Venkateswaran

**Project Link:** https://github.com/KannanVenkateswaran/Medication-Adherence-System-Project

## How it was Made (Second Iteration):

During the second iteration, we identified that the monolithic single-file approach limited maintainability and testability. We refactored the codebase into a modular package architecture with clear separation of concerns.

**Technology Stack:** Python 3.11+, dataclasses for type-safe models, and JSONL for append-only event logging.

**Key Architectural Decisions:**
- **Modularity:** Separated models, business logic, notifications, and CLI into distinct modules for easier testing and maintenance.
- **Dependency Injection:** Injected a configurable clock and SMTP factory, enabling fast, deterministic unit tests without external dependencies or side effects.
- **Event Sourcing:** Used JSONL logs to maintain an immutable audit trail of all medication events.

**Implementation Process:**
1. Extracted core business logic from the original monolithic script
2. Designed the notification abstraction to support injectable email and time dependencies
3. Built comprehensive unit tests with test doubles (FakeNotificationSystem, FixedClock)
4. Added detailed docstrings and updated documentation throughout


## Optimizations

**Testability through Dependency Injection:** By decoupling the system clock and email backend into injectable dependencies, we achieved deterministic, side-effect-free testing. This eliminated flaky tests and significantly reduced execution time.

**Robust Input Parsing:** The time-parsing module normalizes various input formats and gracefully handles edge cases (extra whitespace, inconsistent formatting, quote characters) without throwing exceptions. This prevents user-facing crashes and improves reliability.

**Pragmatic Data Persistence:** JSONL provides a simple, human-readable event log without the overhead of a full database. This choice prioritizes clarity and rapid iteration during development while remaining compatible with future schema evolution.

**Modular Notification System:** The abstraction allows notification channels to be swapped without modifying core business logic. Current implementation uses SMTP; future implementations could support SMS, push notifications, or webhooks.

**Performance Opportunities:** Current optimizations target code clarity and maintainability. Future enhancements could include batch log writes, indexed queries for faster report generation, asynchronous email delivery, and scheduled task caching.

## Repository layout
- `medbase.py` — thin program entrypoint that calls the package CLI.
- `medication_system/` — application package with modules:
	- `models.py` — dataclasses for `Patient`, `MedicationInfo`, and `MedicationLog`.
	- `core.py` — `PatientDirectory`: record doses, detect missed doses, generate reports.
	- `notifications.py` — `NotificationSystem` with injectable SMTP factory for tests.
	- `cli.py` — small interactive menu for manual testing.
- `tests/` — unit tests demonstrating core behaviour and test doubles.

## Quick start
1. Create a Python 3.11+ virtual environment and activate it.
2. Run the unit tests:

```bash
python -m unittest discover -s tests -v
```

3. Launch the interactive CLI (simple demo):

```bash
python medbase.py
```

## Lessons Learned

**Dependency Injection Enables Better Design:** What initially seemed like extra setup work became invaluable. Injecting dependencies reduced coupling, made testing efficient, and simplified debugging. This pattern will be a core part of my future projects.

**Modular Architecture Scales Effort:** Breaking down the monolith into focused modules made the codebase easier to understand, test, and extend. Each module has a single responsibility, which makes both onboarding new developers and adding features straightforward.

**Defensive Input Handling is Essential:** Robust parsing and graceful error handling significantly improve user experience. Rather than failing fast, the system validates input, normalizes formats, and logs warnings—preventing runtime crashes and providing clear feedback.

**Documentation Should Be Concurrent with Development:** Writing docstrings and comments during implementation ensures accuracy and reduces the effort needed for retrospective documentation. Clear inline comments make code self-documenting.

**Simplicity First, Optimize Later:** Choosing JSONL over a complex database, plain templates over sophisticated message builders, and synchronous operations over premature async proved the right call. This left room for thoughtful optimization once real usage patterns were understood.