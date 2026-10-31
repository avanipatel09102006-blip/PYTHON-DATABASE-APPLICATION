# Database Application: Company DB (Flask + SQLite)

    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000  (demo data is created on first run)

Database concepts shown
- Two related tables (departments 1 : many employees), PRIMARY/FOREIGN KEY, UNIQUE, CHECK, INDEX
- ON DELETE RESTRICT: a department with employees cannot be deleted (friendly error)
- JOINs, GROUP BY aggregates (headcount, payroll, average salary), ORDER BY, LIMIT
- Parameterised queries everywhere (no SQL injection), server-side validation
- Read-only SQL console (SELECT only, read-only connection, row + time limits)

UI: tabs, responsive tables that become cards on mobile, modal forms, light print-friendly theme.
