"""Database Application: relational Employee/Department system (Flask + SQLite).
Shows: normalised tables, foreign keys, joins, aggregates, validation,
parameterised queries and a read-only SQL console."""
import re
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request

DB_PATH = Path(__file__).with_name("company.db")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
app = Flask(__name__)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # enforce relationships
    return conn


def init_db():
    with db() as c:
        c.executescript(
            """CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                designation TEXT NOT NULL,
                salary REAL NOT NULL CHECK (salary >= 0),
                hire_date TEXT NOT NULL,
                department_id INTEGER NOT NULL
                    REFERENCES departments(id) ON DELETE RESTRICT);
            CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department_id);"""
        )
        if not c.execute("SELECT 1 FROM departments").fetchone():   # demo data on first run
            c.executemany("INSERT INTO departments (name, location) VALUES (?,?)",
                          [("Engineering", "Ahmedabad"), ("Human Resources", "Mehsana"),
                           ("Finance", "Gandhinagar"), ("Marketing", "Surat")])
            c.executemany(
                "INSERT INTO employees (emp_code,name,email,designation,salary,hire_date,department_id) VALUES (?,?,?,?,?,?,?)",
                [("E001", "Riya Shah", "riya@example.com", "Senior Developer", 95000, "2022-04-11", 1),
                 ("E002", "Karan Mehta", "karan@example.com", "Backend Developer", 72000, "2023-08-01", 1),
                 ("E003", "Neha Joshi", "neha@example.com", "QA Engineer", 54000, "2024-01-15", 1),
                 ("E004", "Amit Desai", "amit@example.com", "HR Manager", 68000, "2021-06-20", 2),
                 ("E005", "Pooja Trivedi", "pooja@example.com", "Recruiter", 42000, "2024-05-06", 2),
                 ("E006", "Vivek Patel", "vivek@example.com", "Accountant", 51000, "2022-11-09", 3),
                 ("E007", "Sneha Modi", "sneha@example.com", "Finance Lead", 88000, "2020-03-02", 3),
                 ("E008", "Harsh Vyas", "harsh@example.com", "SEO Specialist", 47000, "2023-02-14", 4),
                 ("E009", "Divya Nair", "divya@example.com", "Brand Manager", 76000, "2021-09-27", 4),
                 ("E010", "Manav Soni", "manav@example.com", "Frontend Developer", 65000, "2024-09-02", 1)])


def clean(d, key, n):
    return str(d.get(key, "")).strip()[:n]


@app.route("/")
def index():
    return render_template("index.html")


# ---------- Departments ----------
@app.get("/api/departments")
def departments():
    with db() as c:
        rows = c.execute("""SELECT d.id, d.name, d.location, COUNT(e.id) AS employees
                            FROM departments d LEFT JOIN employees e ON e.department_id = d.id
                            GROUP BY d.id ORDER BY d.name""").fetchall()
    return jsonify([dict(r) for r in rows])


def save_department(did=None):
    d = request.get_json(silent=True) or {}
    name, loc = clean(d, "name", 60), clean(d, "location", 60)
    if not name:
        return jsonify(error="Department name is required"), 400
    try:
        with db() as c:
            if did:
                cur = c.execute("UPDATE departments SET name=?, location=? WHERE id=?", (name, loc, did))
                if not cur.rowcount:
                    return jsonify(error="Department not found"), 404
            else:
                did = c.execute("INSERT INTO departments (name, location) VALUES (?,?)", (name, loc)).lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="A department with this name already exists"), 409
    return jsonify(id=did)


app.add_url_rule("/api/departments", "dept_add", lambda: save_department(), methods=["POST"])
app.add_url_rule("/api/departments/<int:did>", "dept_edit", save_department, methods=["PUT"])


@app.delete("/api/departments/<int:did>")
def delete_department(did):
    try:
        with db() as c:
            c.execute("DELETE FROM departments WHERE id=?", (did,))
    except sqlite3.IntegrityError:     # ON DELETE RESTRICT in action
        return jsonify(error="Cannot delete: this department still has employees. Move or remove them first."), 409
    return jsonify(ok=True)


# ---------- Employees ----------
@app.get("/api/employees")
def employees():
    q, dept = request.args.get("q", "").strip(), request.args.get("dept", type=int)
    sort = {"salary": "e.salary DESC", "hired": "e.hire_date DESC", "dept": "d.name, e.name"}.get(
        request.args.get("sort"), "e.name COLLATE NOCASE")
    sql = """SELECT e.*, d.name AS department FROM employees e
             JOIN departments d ON d.id = e.department_id WHERE 1=1"""
    args = []
    if q:
        sql += " AND (e.name LIKE ? OR e.emp_code LIKE ? OR e.designation LIKE ?)"
        args += [f"%{q}%"] * 3
    if dept:
        sql += " AND e.department_id = ?"
        args.append(dept)
    with db() as c:
        return jsonify([dict(r) for r in c.execute(f"{sql} ORDER BY {sort}", args)])


def employee_data():
    d = request.get_json(silent=True) or {}
    try:
        out = {"emp_code": clean(d, "emp_code", 20), "name": clean(d, "name", 80), "email": clean(d, "email", 100),
               "designation": clean(d, "designation", 60), "salary": float(d.get("salary")),
               "hire_date": clean(d, "hire_date", 10), "department_id": int(d.get("department_id"))}
        date.fromisoformat(out["hire_date"])
    except (TypeError, ValueError):
        return None, "Check salary, hire date (YYYY-MM-DD) and department"
    if not (out["emp_code"] and out["name"] and out["designation"]):
        return None, "Employee code, name and designation are required"
    if not EMAIL_RE.match(out["email"]):
        return None, "Enter a valid email address"
    if out["salary"] < 0:
        return None, "Salary cannot be negative"
    return out, None


def save_employee(eid=None):
    data, err = employee_data()
    if err:
        return jsonify(error=err), 400
    try:
        with db() as c:
            if eid:
                cur = c.execute("""UPDATE employees SET emp_code=:emp_code, name=:name, email=:email,
                    designation=:designation, salary=:salary, hire_date=:hire_date,
                    department_id=:department_id WHERE id=:id""", {**data, "id": eid})
                if not cur.rowcount:
                    return jsonify(error="Employee not found"), 404
            else:
                eid = c.execute("""INSERT INTO employees (emp_code,name,email,designation,salary,hire_date,department_id)
                    VALUES (:emp_code,:name,:email,:designation,:salary,:hire_date,:department_id)""", data).lastrowid
    except sqlite3.IntegrityError as e:
        msg = "Selected department does not exist" if "FOREIGN" in str(e).upper() else "This employee code already exists"
        return jsonify(error=msg), 409
    return jsonify(id=eid)


app.add_url_rule("/api/employees", "emp_add", lambda: save_employee(), methods=["POST"])
app.add_url_rule("/api/employees/<int:eid>", "emp_edit", save_employee, methods=["PUT"])


@app.delete("/api/employees/<int:eid>")
def delete_employee(eid):
    with db() as c:
        c.execute("DELETE FROM employees WHERE id=?", (eid,))
    return jsonify(ok=True)


# ---------- Reports ----------
@app.get("/api/reports")
def reports():
    with db() as c:
        t = c.execute("SELECT COUNT(*) n, COALESCE(SUM(salary),0) total, COALESCE(AVG(salary),0) avg FROM employees").fetchone()
        by_dept = c.execute("""SELECT d.name, COUNT(e.id) AS headcount, COALESCE(AVG(e.salary),0) AS avg_salary,
                               COALESCE(SUM(e.salary),0) AS payroll
                               FROM departments d LEFT JOIN employees e ON e.department_id = d.id
                               GROUP BY d.id ORDER BY payroll DESC""").fetchall()
        recent = c.execute("""SELECT e.name, e.designation, e.hire_date, d.name AS department
                              FROM employees e JOIN departments d ON d.id = e.department_id
                              ORDER BY e.hire_date DESC LIMIT 5""").fetchall()
        top = c.execute("""SELECT e.name, e.designation, e.salary FROM employees e
                           ORDER BY e.salary DESC LIMIT 1""").fetchone()
    return jsonify(total=t["n"], payroll=t["total"], avg=round(t["avg"]), top=dict(top) if top else None,
                   by_dept=[dict(r) for r in by_dept], recent=[dict(r) for r in recent])


# ---------- Schema + read-only SQL console ----------
@app.get("/api/schema")
def schema():
    with db() as c:
        tables = [r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        out = {t: [{"name": r["name"], "type": r["type"], "pk": bool(r["pk"])} for r in c.execute(f"PRAGMA table_info({t})")] for t in tables}
    return jsonify(out)


@app.post("/api/query")
def run_query():
    sql = (request.get_json(silent=True) or {}).get("sql", "").strip().rstrip(";")
    if not re.match(r"(?is)^(select|with)\b", sql) or ";" in sql or len(sql) > 2000:
        return jsonify(error="Only a single SELECT query is allowed."), 400
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)   # read-only connection
    ticks = {"n": 0}

    def guard():                       # stop runaway queries
        ticks["n"] += 1
        return 1 if ticks["n"] > 3000 else 0
    conn.set_progress_handler(guard, 1000)
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = [list(r) for r in cur.fetchmany(200)]
    except sqlite3.Error as e:
        return jsonify(error=f"SQL error: {e}"), 400
    finally:
        conn.close()
    return jsonify(columns=cols, rows=rows, truncated=len(rows) == 200)


init_db()
if __name__ == "__main__":
    app.run(debug=True)
