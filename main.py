import json

from flask import Flask, render_template, redirect, url_for, request, jsonify, session, send_file
import pyodbc  # For Microsoft SQL Server connection
from ortools.sat.python import cp_model  # For constraint programming
from collections import defaultdict  # Add this import at the top


app = Flask(__name__)
app.config["SECRET_KEY"] = "e8c9f2d7b4a1c3e5f8a2d9b3c7e1f4a5"  # Ensure this is set
app.config["SESSION_COOKIE_SECURE"] = False  # Set to True in production with HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_PERMANENT"] = True

# Database configuration
DB_CONFIG = {
    "server": "localhost",  # Replace with your SQL Server hostname or IP
    "database": "offeringsDB",  # Replace with your database name
    "username": "sa",  # Replace with your SQL Server username
    "password": "Xbox2001"  # Replace with your SQL Server password
}

time_slots = [
    "MW 8:00-9:15 AM", "MW 9:30-10:45 AM", "MW 11:00 AM-12:15 PM",
    "MW 12:30-1:45 PM", "MW 2:00-3:15 PM", "MW 3:30-4:45 PM",
    "MW 5:00-6:15 PM", "MW 6:30-8:45 PM",
    "TTh 8:00-9:15 AM", "TTh 9:30-11:45 AM", "TTh 11:00 AM-12:15 PM",
    "TTh 12:30-1:45 PM", "TTh 2:00-3:15 PM", "TTh 3:30-4:45 PM",
    "TTh 5:00-6:15 PM", "TTh 6:30-8:45 PM"
]


def get_courses_by_school(school_code):
    """
    Fetch courses from the Course table filtered by fac_code, including course_year and credits.
    """
    try:
        # Create the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        # Establish the database connection
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Modify the query to include the 'credits' column
        query = "SELECT Code, Title, course_year, credits, Capcity FROM Course WHERE fac_code = ?"
        cursor.execute(query, school_code)
        rows = cursor.fetchall()
        connection.close()

        # Construct the list of courses with numeric course_year and credits
        courses_list = [
            {
                "Code": row[0],
                "Title": row[1],
                "course_year": map_course_year_to_numeric(row[2]),
                "credits": row[3],
                "capacity": row[4]  # Add capacity to the result
            }
            for row in rows
        ]
        return courses_list
    except Exception as e:
        print(f"Error fetching courses from database: {e}")
        return []


def get_service_courses(school_code):
    """
    Fetch courses from other faculties (excluding the given school_code).
    Returns list of course dictionaries including Code, Title, course_year, credits, Capcity.
    """
    try:
        # Create the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # First get all distinct fac_codes excluding the current one
        cursor.execute("SELECT DISTINCT fac_code FROM Course")
        all_faculties = [row[0] for row in cursor.fetchall()]
        other_faculties = [f for f in all_faculties if f != school_code]

        print(f"[DEBUG] Fetching service courses from faculties: {other_faculties}")

        if not other_faculties:
            print("[INFO] No other faculties found to fetch service courses.")
            return []

        # Build query with IN clause for multiple faculties
        placeholders = ','.join(['?'] * len(other_faculties))
        query = f"""
            SELECT Code, Title, course_year, credits, Capcity 
            FROM Course 
            WHERE fac_code IN ({placeholders})
        """
        cursor.execute(query, other_faculties)
        rows = cursor.fetchall()
        connection.close()

        # Map results to list of dicts
        courses_list = [
            {
                "Code": row[0],
                "Title": row[1],
                "course_year": map_course_year_to_numeric(row[2]),
                "credits": row[3],
                "capacity": row[4]
            }
            for row in rows
        ]
        return courses_list

    except Exception as e:
        print(f"[ERROR] Error fetching service courses: {e}")
        return []

@app.route("/add-service-courses")
def add_service_courses():
    school_code = request.args.get("school_code")
    campus_code = request.args.get("campus_code")
    academic_year = request.args.get("academic_year")
    semester = request.args.get("semester")

    service_courses = get_service_courses(school_code)

    return render_template(
            "add_service_courses.html",
            service_courses=service_courses,
            school_code=school_code,
            campus_code=campus_code,
            academic_year=academic_year,
            semester=semester
        )

@app.route("/select-service-courses", methods=["POST"])
def select_service_courses():
    selected_courses = request.form.getlist("selected_courses")
    school_code = request.form["school_code"]
    campus_code = request.form["campus_code"]
    academic_year = request.form["academic_year"]
    semester = request.form["semester"]

    print(f"[DEBUG] Selected service courses: {selected_courses}")

    # Save selected service courses in session (or database)
    session["selected_service_courses"] = selected_courses

    # Redirect back to course selection page with updated context
    return redirect(url_for(
        "course_selection",
        school_code=school_code,
        campus_code=campus_code,
        academic_year=academic_year,
        semester=semester
    ))

def validate_instructor_credits(instructor_assignments, max_credits=21):
    """
    Validate that no instructor is assigned more than the allowed maximum credits.

    :param instructor_assignments: Dictionary mapping instructor IDs to their assigned courses and credits.
    :param max_credits: Maximum allowed credits per instructor (default 21).
    :return: True if valid, False otherwise.
    """
    for instructor_id, assignments in instructor_assignments.items():
        total_credits = sum(assignment['credits'] for assignment in assignments)
        if total_credits > max_credits:
            print(f"Instructor {instructor_id} has {total_credits} credits (max {max_credits} allowed).")
            return False
    return True



def map_course_year_to_numeric(course_year):
    """
    Map course_year string to numeric values for dropdown selection.
    Accounts for lab courses by treating them as part of the same year.
    """
    # Define the mapping of course years to numeric values
    mapping = {
        "Freshman Course": 1,
        "Remedial Course": 1,  # Treat remedial as first-year
        "First-year course": 1,
        "Second-year course": 2,
        "Third-year course": 3,
        "Fourth-year course": 4,
        "Fifth-year course": 5,
        "Advanced or Special Course": 6  # Default to advanced
    }

    # Normalize the input by removing "(Lab)" or similar indicators
    normalized_course_year = course_year.split(" (")[0].strip()

    # Return the mapped value or default to 1 if no match
    return mapping.get(normalized_course_year, 1)


def get_Faculty_from_db():
    """Fetch unique fac_code values from the instructor table."""
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()
        query = "SELECT faccode FROM Faculty"
        print(f"Executing query: {query}")
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} schools from the database.")
        cursor.close()
        connection.close()
        schools_list = [{"school_code": row[0]} for row in rows]
        return schools_list
    except Exception as e:
        print(f"Error fetching schools from database: {e}")
        return []

def get_instructors_by_school(school_code):
    """Fetch instructors from the database based on the selected school's fac_code where Active = 1."""
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print(f"Connecting to database to fetch instructors for school_code: {school_code}")
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()
        query = """
            SELECT facuser, title, fname, mname, lname, accountEmail, Division, fac_code
            FROM Instructor 
            WHERE fac_code = ? AND Active = 1
        """
        print(f"Executing query: {query} with param: {school_code}")
        cursor.execute(query, school_code)
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} ACTIVE instructors from the database.")
        cursor.close()
        connection.close()

        instructors_list = [
            {
                "identifier": row[0],
                "facuser": row[0],
                "title": row[1],
                "fname": row[2],
                "mname": row[3],
                "lname": row[4],
                "accountEmail": row[5],
                "Division": row[6],
                "fac_code": row[7],
            }
            for row in rows
        ]
        return instructors_list
    except Exception as e:
        print(f"Error fetching instructors from database: {e}")
        return []

@app.route("/")
def home():
    """
    Redirect the root URL to the school selection page.
    """
    return redirect(url_for("index"))


@app.route("/select-faculty")
def select_faculty():
    schools =  get_Faculty_from_db()
    campuses = get_campuses_from_db()

    # Generate the current academic year dynamically
    from datetime import datetime
    current_year = datetime.now().year
    next_year = current_year + 1
    academic_years = [f"{current_year}-{next_year}", f"{next_year}-{next_year + 1}"]

    # Define semesters
    semesters = ["Fall", "Spring", "Summer"]

    print(f"Rendering school selection page with {len(schools)} schools and {len(campuses)} campuses.")
    return render_template(
        "school_selection.html",
        schools=schools,
        campuses=campuses,
        academic_years=academic_years,  # Pass academic years to the template
        semesters=semesters  # Pass semesters to the template
    )

def get_campuses_from_db():
    """
    Fetch unique campusID and location values from the campuses table.
    """
    try:
        # Construct the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print("Connecting to database to fetch campuses.")

        # Establish the database connection
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Define the query to fetch campusID and location
        query = "SELECT DISTINCT campusID, location FROM campus"
        print(f"Executing query: {query}")

        # Execute the query and fetch all rows
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} campuses from the database.")

        # Close the cursor and connection
        cursor.close()
        connection.close()

        # Format the result as a list of dictionaries
        campuses_list = [{"campus_code": row[0], "location": row[1]} for row in rows]
        return campuses_list

    except Exception as e:
        print(f"Error fetching campuses from database: {e}")
        return []

@app.route("/previous_semester")
def previous_semester():
    schools = get_Faculty_from_db()
    campuses = get_campuses_from_db()

    # Generate academic years including past years
    from datetime import datetime
    current_year = datetime.now().year
    next_year = current_year + 1
    prev_year = current_year - 1
    academic_years = [f"{prev_year}-{current_year}", f"{current_year}-{next_year}", f"{next_year}-{next_year + 1}"]

    # Define semesters
    semesters = ["Fall", "Spring", "Summer"]

    print(f"Rendering previous semester page with {len(schools)} schools and {len(campuses)} campuses.")
    return render_template(
        "previous_semester.html",
        schools=schools,
        campuses=campuses,
        academic_years=academic_years,
        semesters=semesters
    )
@app.route("/view_previous_semester", methods=["POST"])
def view_previous_semester():
    """
    Retrieve schedule data from the database based on the selected parameters
    and display it in the previous_semester.html template.
    """
    # Get form data
    school_code = request.form.get("school_code")
    campus_code = request.form.get("campus_code")
    academic_year = request.form.get("academic_year")
    semester = request.form.get("semester")

    print(f"Retrieving schedule for School: {school_code}, Campus: {campus_code}, Year: {academic_year}, Semester: {semester}")

    try:
        # Create the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )

        # Establish the database connection
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Query to retrieve schedule data
        query = """
        SELECT CourseNumber, Code, Section, FACUSER, Room, 
               STIME, ETIME, M, T, W, TH, F, S, 
               Campus, University, AllowCross, SchedulingType, 
               BypassPayroll, Capacity
        FROM Schedule 
        WHERE Year = ? AND Semester = ? AND fac_code = ? AND Campus = ?
        ORDER BY CourseNumber
        """
        cursor.execute(query, (academic_year, semester, school_code, campus_code))
        rows = cursor.fetchall()

        # Convert rows to a list of dictionaries for easier handling in the template
        schedule_data = []
        for row in rows:
            schedule_data.append({
                "CourseNumber": row[0],
                "Code": row[1],
                "Section": row[2],
                "FACUSER": row[3],
                "Room": row[4],
                "STIME": row[5],
                "ETIME": row[6],
                "M": 1 if row[7] else 0,
                "T": 1 if row[8] else 0,
                "W": 1 if row[9] else 0,
                "TH": 1 if row[10] else 0,
                "F": 1 if row[11] else 0,
                "S": 1 if row[12] else 0,
                "Campus": row[13],
                "University": row[14],
                "AllowCross": row[15],
                "SchedulingType": row[16],
                "BypassPayroll": row[17],
                "Capacity": row[18]
            })

        # Close the connection
        cursor.close()
        connection.close()

        # Get schools and campuses for the form
        schools = get_Faculty_from_db()
        campuses = get_campuses_from_db()

        # Generate academic years including past years
        from datetime import datetime
        current_year = datetime.now().year
        next_year = current_year + 1
        prev_year = current_year - 1
        academic_years = [f"{prev_year}-{current_year}", f"{current_year}-{next_year}", f"{next_year}-{next_year + 1}"]

        # Define semesters
        semesters = ["Fall", "Spring", "Summer"]

        print(f"Retrieved {len(schedule_data)} schedule records.")
        return render_template(
            "previous_semester.html",
            schools=schools,
            campuses=campuses,
            academic_years=academic_years,
            semesters=semesters,
            schedule_data=schedule_data,
            selected_school=school_code,
            selected_campus=campus_code,
            selected_year=academic_year,
            selected_semester=semester
        )

    except Exception as e:
        print(f"Error retrieving schedule data: {e}")
        # Get schools and campuses for the form
        schools = get_schools_from_db()
        campuses = get_campuses_from_db()

        # Generate academic years including past years
        from datetime import datetime
        current_year = datetime.now().year
        next_year = current_year + 1
        prev_year = current_year - 1
        academic_years = [f"{prev_year}-{current_year}", f"{current_year}-{next_year}", f"{next_year}-{next_year + 1}"]

        # Define semesters
        semesters = ["Fall", "Spring", "Summer"]

        return render_template(
            "previous_semester.html",
            schools=schools,
            campuses=campuses,
            academic_years=academic_years,
            semesters=semesters,
            error=f"Error retrieving schedule data: {e}"
        )

@app.route("/submit_school", methods=["POST"])
def submit_school():
    school_code = request.form.get("school_code")
    campus_code = request.form.get("campus_code")
    academic_year = request.form.get("academic_year")
    semester = request.form.get("semester")

    print(f"Selected School Code: {school_code}, Campus Code: {campus_code}")
    print(f"Selected Academic Year: {academic_year}, Semester: {semester}")

    # Redirect to the next page, passing all selected values
    return redirect(url_for(
        "instructor_availability",
        school_code=school_code,
        campus_code=campus_code,
        academic_year=academic_year,
        semester=semester
    ))

def get_instructors_by_campus(campus_code, school_code, year, semester):
    """
    Fetch instructors:
    - All active instructors from the specified campus (campus_code)
    - Plus active instructors from other campuses who have availability in the specified campus
      for the given year and semester.
    """
    try:
        # Create the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        # Establish the database connection
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Query to get instructors from the current campus OR available there this term
        query = """
            SELECT DISTINCT i.facuser, i.fac_code, i.campusID, i.title, i.fname, i.mname, i.lname
            FROM Instructor i
            LEFT JOIN Instructor_Availability ia 
                ON i.facuser = ia.facuser
                AND ia.year = ?
                AND ia.semester = ?
            WHERE i.Active = 1
              AND i.fac_code = ?
              AND (i.campusID = ? OR ia.campusID = ?)
        """
        cursor.execute(query, year, semester, school_code, campus_code, campus_code)
        rows = cursor.fetchall()
        connection.close()

        # Construct the list of instructors
        instructors_list = [
            {
                "facuser": row[0],
                "fac_code": row[1],
                "campusID": row[2],
                "title": row[3],
                "fname": row[4],
                "mname": row[5],
                "lname": row[6]
            }
            for row in rows
        ]
        return instructors_list
    except Exception as e:
        print(f"Error fetching instructors from database: {e}")
        return []

def generate_summer_schedule():
    try:
        # Define time slots for regular courses and lab courses
        regular_time_slots = ['MWTTH 8:00-9:50', 'MWTTH 10:00-11:50', 'MWTTH 12:00-1:50']
        lab_time_slots = ['MWTH 8:00-9:50', 'MWTH 10:00-11:50', 'MWTH 12:00-1:50']

        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))

        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}
        course_semesters = {}  # FIXED: Added initialization here

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")
        academic_year = request.form.get("academic_year")

        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400

        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400

        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        if not instructor_availability:
            return jsonify({"error": "Instructor availability data is missing."}), 400

        # Debugging: Log the instructor availability data
        print(f"Instructor Availability Data: {instructor_availability}")

        # Process selected courses
        all_sections = []
        selected_courses = request.form.getlist("courses")
        for course_with_section in selected_courses:
            base_course, section_letter = course_with_section.rsplit("_", 1)
            num_students = int(request.form[f"students_{course_with_section}"])
            instructor_key = f"instructor_{course_with_section}"
            instructor = request.form.get(instructor_key, "TBA")  # Default to TBA
            instructor_assignments[course_with_section] = instructor
            year = int(request.form[f"year_{course_with_section}"])
            semester = get_semester(base_course)
            course_semesters[course_with_section] = semester  # This line now works

            # Check if the course is a lab course based on its title
            is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
            time_slots = lab_time_slots if is_lab_course else regular_time_slots

            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the appropriate time_slots array
                if time_str not in time_slots:
                    raise ValueError(f"Invalid time slot: {time_str}")

                # Validate instructor availability for the specified time
                if time_str not in instructor_availability.get(instructor, []):
                    instr_name = next((i["facuser"] for i in instructors if i["identifier"] == instructor), "Unknown")
                    print(f"Instructor {instr_name} availability: {instructor_availability.get(instructor, [])}")
                    raise ValueError(f"Instructor {instr_name} unavailable at {time_str} for {course_with_section}")

                fixed_times[course_with_section] = time_slots.index(time_str)  # Store index for CP model

            # Assign instructor and year to the course section
            instructor_assignments[course_with_section] = instructor
            course_years[course_with_section] = year

            # Group sections by base course
            if base_course not in course_sections:
                course_sections[base_course] = []
            course_sections[base_course].append(course_with_section)
            all_sections.append(course_with_section)

        # Create CP model
        model = cp_model.CpModel()
        slot_vars = {s: model.NewIntVar(0, len(regular_time_slots) - 1, f"slot_{s}") for s in all_sections}

        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)

        # Add availability constraints for each course section
        for course_with_section in all_sections:
            base_course, _ = course_with_section.rsplit("_", 1)
            is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
            time_slots = lab_time_slots if is_lab_course else regular_time_slots

            instr_id = instructor_assignments[course_with_section]
            allowed = instructor_availability.get(instr_id, [])

            # If time is fixed, only allow that slot
            if course_with_section in fixed_times:
                allowed = [fixed_times[course_with_section]]
            else:
                # Convert time slots to indexes
                allowed = [time_slots.index(ts) for ts in allowed if ts in time_slots]

            if allowed:
                model.AddAllowedAssignments([slot_vars[course_with_section]], [[slot] for slot in allowed])
            else:
                print(f"No valid time slots available for instructor {instr_id}. Skipping constraint.")

            # Initialize penalty variables
            penalty_vars = []

        # Add conflict constraints
        # Inside the loop over course pairs (i and j):
        for i in range(len(all_sections)):
            for j in range(i + 1, len(all_sections)):
                s1 = all_sections[i]
                s2 = all_sections[j]

                # Only apply same-instructor constraint if both have assigned instructors (not TBA)
                inst1 = instructor_assignments[s1]
                inst2 = instructor_assignments[s2]
                if inst1 == inst2 and inst1 != "TBA":
                    model.Add(slot_vars[s1] != slot_vars[s2])

                # Check same year and different courses
                if (course_years[s1] == course_years[s2] and
                        s1.split("_")[0] != s2.split("_")[0]):

                    # Get semesters of the two courses
                    sem1 = course_semesters[s1]
                    sem2 = course_semesters[s2]

                    if sem1 == sem2:  # Same semester → add penalty
                        same_slot = model.NewBoolVar(f'same_{s1}_{s2}')
                        model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(same_slot)
                        model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(same_slot.Not())
                        penalty_vars.append(same_slot)
                    # Else: Different semesters → no penalty (allowed to overlap)

        # Calculate total penalty for same-year conflicts
        total_penalty = model.NewIntVar(0, len(penalty_vars), 'total_penalty')
        model.Add(total_penalty == sum(penalty_vars))



        # Objective function: Minimize the maximum time slot used
        max_time = model.NewIntVar(0, len(regular_time_slots) - 1, "max_time")
        model.AddMaxEquality(max_time, [slot_vars[s] for s in all_sections])
        # Update the objective to minimize both max_time and penalties
        model.Minimize(max_time + total_penalty * 100)  # Adjust the penalty weight as needed (e.g., 100)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Log solver status and statistics
        print(f"Status: {solver.StatusName(status)}")
        print(f"Number of variables: {len(slot_vars)}")
        print(f"Number of constraints: {model.Proto().constraints.__len__()}")

        # Check if a feasible solution was found
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = {}
            for section in all_sections:
                base_course, _ = section.rsplit("_", 1)
                is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
                time_slots = lab_time_slots if is_lab_course else regular_time_slots

                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(max_time)
            schedule["completion_time"] = regular_time_slots[max_slot]

            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: (lab_time_slots + regular_time_slots).index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]

            # Debugging: Log the generated schedule
            print(f"Generated Schedule: {sorted_schedule}")

            # Function to filter courses with 'TBA' instructors
            def filter_tba_courses(schedule):
                filtered_schedule = {}

                for key, value in schedule.items():
                    # Only check course entries (skip completion_time or other metadata)
                    if isinstance(value, dict) and 'instructor' in value:
                        if value['instructor'] != 'TBA':
                            filtered_schedule[key] = value
                    else:
                        # Keep non-course keys like 'completion_time'
                        filtered_schedule[key] = value

                return filtered_schedule

            # Apply filtering
            filtered_schedule = filter_tba_courses(sorted_schedule)

            # Print result
            print(f"Generated Relaxed Schedule: {filtered_schedule}")

            semester = request.form.get("semester")

            save_result = save_schedule_to_database(
                filtered_schedule,
                school_code,
                campus_code,
                academic_year,
                semester
            )

            if not save_result:
                print("Warning: Failed to save schedule to database")
            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/schedule", methods=["POST"])
def schedule_handler():
    try:
        # Retrieve session data
        instructor_availability = session.get("instructor_availability", {})
        if not instructor_availability:
            # Re-fetch instructor availability if missing
            school_code = request.form.get("school_code")
            campus_code = request.form.get("campus_code")  # Include campus_code
            academic_year = request.form.get("academic_year")
            semester = request.form.get("semester")
            if not school_code or not campus_code or not academic_year or not semester:
                return jsonify({"error": "Required parameters are missing."}), 400

            # Fetch instructor availability based on school_code, campus_code, academic_year, and semester
            response, status_code = fetch_instructor_availability_internal_for_course_selection(
                school_code, academic_year, semester, campus_code  # Pass campus_code
            )
            if "error" in response:
                return jsonify({"error": response["error"]}), status_code

            # Update session with the fetched instructor availability
            instructor_availability = response.get("instructor_availability", {})
            session["instructor_availability"] = instructor_availability

        # Debugging: Log the instructor availability
        print(f"[DEBUG] Instructor availability retrieved: {instructor_availability}")

        # Continue with scheduling logic...
        semester = request.form.get("semester")
        print(semester)

        # Validate semester
        if not semester:
            return jsonify({"error": "Semester information is missing."}), 400

        # Redirect to the appropriate function based on the semester
        if semester.lower() == "summer":
            return generate_summer_schedule()
        else:
            return generate_relaxed_schedule()

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

'''def generate_schedule():
    try:
        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))

        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")

        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400

        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400

        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        print(f"[DEBUG] Session instructor_availability retrieved: {instructor_availability}")
        if not instructor_availability:
            return jsonify({"error": "Instructor availability data is missing."}), 400

        # Debugging: Log the instructor availability data
        print(f"Instructor Availability Data: {instructor_availability}")

        # Process selected courses
        all_sections = []
        selected_courses = request.form.getlist("courses")
        for course_with_section in selected_courses:
            base_course, section_letter = course_with_section.rsplit("_", 1)
            num_students = int(request.form[f"students_{course_with_section}"])
            instructor = request.form[f"instructor_{course_with_section}"]
            year = int(request.form[f"year_{course_with_section}"])

            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the global time_slots array
                if time_str not in time_slots:
                    raise ValueError(f"Invalid time slot: {time_str}")

                # Validate instructor availability for the specified time
                if time_str not in instructor_availability.get(instructor, []):
                    instr_name = next((i["facuser"] for i in instructors if i["identifier"] == instructor), "Unknown")
                    print(f"Instructor {instr_name} availability: {instructor_availability.get(instructor, [])}")
                    raise ValueError(f"Instructor {instr_name} unavailable at {time_str} for {course_with_section}")

                fixed_times[course_with_section] = time_slots.index(time_str)  # Store index for CP model

            # Assign instructor and year to the course section
            instructor_assignments[course_with_section] = instructor
            course_years[course_with_section] = year

            # Group sections by base course
            if base_course not in course_sections:
                course_sections[base_course] = []
            course_sections[base_course].append(course_with_section)
            all_sections.append(course_with_section)

        # Create CP model
        model = cp_model.CpModel()
        slot_vars = {s: model.NewIntVar(0, len(time_slots) - 1, f"slot_{s}") for s in all_sections}

        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)

        # Handle lab constraints
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)

        # Enforce same course lab sections to have the same slot
        same_course_groups = defaultdict(list)
        for s in lab_sections:
            base = s.rsplit('_', 1)[0]
            same_course_groups[base].append(s)
        for group in same_course_groups.values():
            if len(group) < 2:
                continue
            first = group[0]
            for s in group[1:]:
                model.Add(slot_vars[s] == slot_vars[first])


        # Handle same instructor labs (different courses) with penalties
        penalties = []
        instructor_lab_sections = defaultdict(list)
        for s in lab_sections:
            instr = instructor_assignments[s]
            instructor_lab_sections[instr].append(s)
        for instr, labs in instructor_lab_sections.items():
            for i in range(len(labs)):
                for j in range(i + 1, len(labs)):
                    s1 = labs[i]
                    s2 = labs[j]
                    base1 = s1.rsplit('_', 1)[0]
                    base2 = s2.rsplit('_', 1)[0]
                    if base1 == base2:
                        continue  # already grouped by same course
                    diff_var = model.NewBoolVar(f'diff_{s1}_{s2}')
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff_var)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff_var.Not())
                    penalties.append(diff_var)

        # --- NEW CONSTRAINT: MAX 2 LABS PER TIME SLOT ---
        # Collect all lab sections
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)

        # Ensure no time slot has more than 2 lab courses
        for i in range(len(lab_sections)):
            for j in range(i + 1, len(lab_sections)):
                for k in range(j + 1, len(lab_sections)):
                    s1 = lab_sections[i]
                    s2 = lab_sections[j]
                    s3 = lab_sections[k]

                    # Create boolean variables to track differences
                    diff1 = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff1)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff1.Not())

                    diff2 = model.NewBoolVar(f"{s1}_{s3}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s3]).OnlyEnforceIf(diff2)
                    model.Add(slot_vars[s1] == slot_vars[s3]).OnlyEnforceIf(diff2.Not())

                    diff3 = model.NewBoolVar(f"{s2}_{s3}_diff")
                    model.Add(slot_vars[s2] != slot_vars[s3]).OnlyEnforceIf(diff3)
                    model.Add(slot_vars[s2] == slot_vars[s3]).OnlyEnforceIf(diff3.Not())

                    # At least one difference must be true
                    model.AddBoolOr([diff1, diff2, diff3])

        # --- NEW CONSTRAINT: SAME YEAR COURSES CANNOT CONFLICT ---
        # Group courses by year and base course
        courses_by_year = defaultdict(dict)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            year = course_years[section]
            if year not in courses_by_year:
                courses_by_year[year] = {}
            if base_course not in courses_by_year[year]:
                courses_by_year[year][base_course] = []
            courses_by_year[year][base_course].append(section)

        # Ensure no overlapping slots for different base courses in the same year
        for year, base_courses in courses_by_year.items():
            # For all pairs of different base courses in the same year
            base_list = list(base_courses.keys())
            for i in range(len(base_list)):
                for j in range(i + 1, len(base_list)):
                    bc1 = base_list[i]
                    bc1_sections = base_courses[bc1]
                    bc2 = base_list[j]
                    bc2_sections = base_courses[bc2]
                    # Ensure no section from bc1 and bc2 share the same slot
                    for s1 in bc1_sections:
                        for s2 in bc2_sections:
                            model.Add(slot_vars[s1] != slot_vars[s2])

        # Add availability constraints for each course section
        for course_with_section in all_sections:
            instr_id = instructor_assignments[course_with_section]
            allowed = instructor_availability.get(instr_id, [])

            # If time is fixed, only allow that slot
            if course_with_section in fixed_times:
                allowed = [fixed_times[course_with_section]]
            else:
                # Convert time slots to indexes
                allowed = [time_slots.index(ts) for ts in allowed if ts in time_slots]

            if allowed:
                model.AddAllowedAssignments([slot_vars[course_with_section]], [[slot] for slot in allowed])
            else:
                print(f"No valid time slots available for instructor {instr_id}. Skipping constraint.")

                # Add constraints between course sections
        for i in range(len(all_sections)):
            for j in range(i + 1, len(all_sections)):
                s1 = all_sections[i]
                s2 = all_sections[j]
                # Same instructor constraint with exception for labs
                if instructor_assignments[s1] == instructor_assignments[s2]:
                    # Check if both are lab courses
                    base1 = s1.rsplit("_", 1)[0]
                    base2 = s2.rsplit("_", 1)[0]
                    if base1.endswith('L') and base2.endswith('L'):
                        # Allow same instructor for labs to share a slot
                        continue
                    else:
                        model.Add(slot_vars[s1] != slot_vars[s2])
                    # Same year but different course constraint
                    if course_years[s1] == course_years[s2] and s1.rsplit("_", 1)[0] != s2.rsplit("_", 1)[0]:
                        model.Add(slot_vars[s1] != slot_vars[s2])

                # Group sections by instructor
            instructor_sections = defaultdict(list)
            for section in all_sections:
                    instr_id = instructor_assignments[section]
                    instructor_sections[instr_id].append(section)

            for instr_id, sections in instructor_sections.items():
                # Filter out lab sections (base course ends with 'L')
                non_lab_sections = []
                for s in sections:
                    base_course = s.rsplit('_', 1)[0]
                    if not base_course.endswith('L'):
                        non_lab_sections.append(s)

                # Only apply the constraint if there are 3+ non-lab courses
                n = len(non_lab_sections)
                if n < 3:
                    continue

                times = [slot_vars[section] for section in non_lab_sections]
                for i in range(n):
                    for j in range(i + 1, n):
                        for k in range(j + 1, n):
                            a, b, c = times[i], times[j], times[k]
                            max_var = model.NewIntVar(0, len(time_slots) - 1, f'max_{instr_id}_{i}_{j}_{k}')
                            model.AddMaxEquality(max_var, [a, b, c])
                            min_var = model.NewIntVar(0, len(time_slots) - 1, f'min_{instr_id}_{i}_{j}_{k}')
                            model.AddMinEquality(min_var, [a, b, c])
                            diff = model.NewIntVar(-len(time_slots), len(time_slots), f'diff_{instr_id}_{i}_{j}_{k}')
                            model.Add(diff == max_var - min_var)
                            model.Add(diff > 2)  # Ensure non-lab courses aren't too close

                    # Set the objective function
        max_time = model.NewIntVar(0, len(time_slots) - 1, "max_time")
        model.AddMaxEquality(max_time, [slot_vars[s] for s in all_sections])
        if penalties:
                sum_penalty = model.NewIntVar(0, len(penalties), "sum_penalty")
                model.Add(sum_penalty == sum(penalties))
                model.Minimize(max_time + sum_penalty)
        else:
                model.Minimize(max_time)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Log solver status and statistics
        print(f"Status: {solver.StatusName(status)}")
        print(f"Number of variables: {len(slot_vars)}")
        print(f"Number of constraints: {model.Proto().constraints.__len__()}")

        # Check if a feasible solution was found
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = {}
            for section in all_sections:
                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(max_time)
            schedule["completion_time"] = time_slots[max_slot]

            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: time_slots.index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]

            # Debugging: Log the generated schedule
            print(f"Generated Schedule: {sorted_schedule}")

            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        # Attempt to generate a relaxed schedule as a fallback
        print("Attempting to generate a relaxed schedule...")
        relaxed_schedule_response = generate_relaxed_schedule()

        # Check if the response is a tuple (common in Flask when returning JSON + status code)
        if isinstance(relaxed_schedule_response, tuple):
            relaxed_schedule, status_code = relaxed_schedule_response  # Unpack the tuple
        else:
            relaxed_schedule, status_code = relaxed_schedule_response, 200  # Assume success if not a tuple

        # If the relaxed schedule was successfully generated, return it
        if status_code == 200:
            print("Relaxed schedule generated successfully.")
            return relaxed_schedule  # Return the relaxed schedule
        else:
            # If both methods fail, return the original error and the relaxed schedule error
            relaxed_error = relaxed_schedule.json.get("error", "Unknown error in relaxed schedule.") if hasattr(
                relaxed_schedule, "json") else "Unknown error"
            return jsonify({"error": str(e), "relaxed_error": relaxed_error}), 500
'''

def get_prerequisites(selected_courses):
    """
    Fetch prerequisite relationships involving any of the selected courses.

    Args:
        selected_courses (list): List of base course codes (e.g., ["CSCI200", "CSCI250"]).

    Returns:
        defaultdict(list): A dictionary mapping course codes to their prerequisites.
    """
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print("Connecting to database to fetch filtered prerequisites.")

        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Build dynamic SQL query for filtering
        placeholder = ','.join('?' for _ in selected_courses)
        query = f"""
            SELECT Code, Pre_requisites
            FROM offeringsDB.dbo.pre_requisites
            WHERE Code IN ({placeholder}) OR Pre_requisites IN ({placeholder})
        """
        params = selected_courses * 2  # Reuse the list for both parts of WHERE clause
        print(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)

        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} filtered prerequisite relationships.")

        prereq_map = defaultdict(list)
        for row in rows:
            course_code = row[0].strip() if row[0] else ""
            prereq_code = row[1].strip() if row[1] else ""
            if course_code and prereq_code:
                prereq_map[course_code].append(prereq_code)

        cursor.close()
        connection.close()

        return prereq_map

    except Exception as e:
        print(f"Error fetching filtered prerequisites: {e}")
        return defaultdict(list)

def generate_relaxed_schedule():
    try:
        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))
        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")
        academic_year = request.form.get("academic_year")
        semester = request.form.get("semester")
        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400
        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400
        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        print(f"[DEBUG] Session instructor_availability retrieved: {instructor_availability}")
        if not instructor_availability:
            return jsonify({"error": "Instructor availability data is missing."}), 400
        # Debugging: Log the instructor availability data
        print(f"Instructor Availability Data: {instructor_availability}")
        # Process selected courses
        all_sections = []
        selected_courses = request.form.getlist("courses")
        selected_base_courses = [course.rsplit("_", 1)[0] for course in selected_courses]

        # Fetch only relevant prerequisites
        prereq_map = get_prerequisites(selected_base_courses)
        if not prereq_map:
            print("No prerequisites found for the selected courses.")
        for course_with_section in selected_courses:
            base_course, section_letter = course_with_section.rsplit("_", 1)
            instructor_key = f"instructor_{course_with_section}"
            instructor = request.form.get(instructor_key, "TBA")  # Default to TBA
            instructor_assignments[course_with_section] = instructor
            year = int(request.form[f"year_{course_with_section}"])
            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the global time_slots array
                if time_str not in time_slots:
                    raise ValueError(f"Invalid time slot: {time_str}")
                # Validate instructor availability for the specified time
                if time_str not in instructor_availability.get(instructor, []):
                    instr_name = next((i["facuser"] for i in instructors if i["identifier"] == instructor), "Unknown")
                    print(f"Instructor {instr_name} availability: {instructor_availability.get(instructor, [])}")
                    raise ValueError(f"Instructor {instr_name} unavailable at {time_str} for {course_with_section}")
                fixed_times[course_with_section] = time_slots.index(time_str)  # Store index for CP model
            # Assign instructor and year to the course section
            instructor_assignments[course_with_section] = instructor
            course_years[course_with_section] = year
            # Group sections by base course
            if base_course not in course_sections:
                course_sections[base_course] = []
            course_sections[base_course].append(course_with_section)
            all_sections.append(course_with_section)
        # Create CP model
        model = cp_model.CpModel()
        slot_vars = {s: model.NewIntVar(0, len(time_slots) - 1, f"slot_{s}") for s in all_sections}
        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)
        # Handle lab constraints
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)
        same_course_groups = defaultdict(list)
        # Add an objective to minimize the number of distinct time slots for same-course labs
        objective = model.NewIntVar(0, len(all_sections), "objective")
        for base in same_course_groups:
            group = same_course_groups[base]
            if len(group) < 2:
                continue
            # Create a variable for each pair of sections in the group
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    s1 = group[i]
                    s2 = group[j]
                    # If s1 and s2 are in different slots, add 1 to the objective
                    diff = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff.Not())
                    model.Add(objective + diff <= objective + 1)
        # Minimize the objective (prioritize same slots)
        model.Minimize(objective)
        # --- NEW CONSTRAINT: MAX 2 LABS PER TIME SLOT ---
        # Collect all lab sections
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)
        # Ensure no time slot has more than 2 lab courses
        for i in range(len(lab_sections)):
            for j in range(i + 1, len(lab_sections)):
                for k in range(j + 1, len(lab_sections)):
                    s1 = lab_sections[i]
                    s2 = lab_sections[j]
                    s3 = lab_sections[k]
                    # Create boolean variables to track differences
                    diff1 = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff1)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff1.Not())
                    diff2 = model.NewBoolVar(f"{s1}_{s3}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s3]).OnlyEnforceIf(diff2)
                    model.Add(slot_vars[s1] == slot_vars[s3]).OnlyEnforceIf(diff2.Not())
                    diff3 = model.NewBoolVar(f"{s2}_{s3}_diff")
                    model.Add(slot_vars[s2] != slot_vars[s3]).OnlyEnforceIf(diff3)
                    model.Add(slot_vars[s2] == slot_vars[s3]).OnlyEnforceIf(diff3.Not())
                    # At least one difference must be true
                    model.AddBoolOr([diff1, diff2, diff3])
        # --- RELAXED CONSTRAINT: SAME YEAR COURSES CAN OVERLAP BASED ON SEMESTER ---
        # Group courses by year and base course
        courses_by_year = defaultdict(dict)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            year = course_years[section]
            if year not in courses_by_year:
                courses_by_year[year] = defaultdict(list)
            courses_by_year[year][base_course].append(section)

        # Allow overlapping for courses from the same year if they are prerequisites or different semesters
        for year, base_courses in courses_by_year.items():
            base_list = list(base_courses.keys())
            for i in range(len(base_list)):
                for j in range(i + 1, len(base_list)):
                    bc1 = base_list[i]
                    bc1_sections = base_courses[bc1]
                    bc2 = base_list[j]
                    bc2_sections = base_courses[bc2]

                    # Extract semester information
                    semester_bc1 = get_semester(bc1)
                    semester_bc2 = get_semester(bc2)

                    # Allow overlap for different semesters
                    if semester_bc1 != semester_bc2:
                        print(f"Allowing overlap between {bc1} and {bc2} due to different semesters.")
                        continue

                    # Check for prerequisite relationship
                    is_prereq = False
                    if bc2 in prereq_map.get(bc1, []) or bc1 in prereq_map.get(bc2, []):
                        is_prereq = True

                    if is_prereq:
                        print(f"Allowing overlap between {bc1} and {bc2} due to prerequisite relationship.")
                    else:
                        print(f"Preventing overlap between {bc1} and {bc2}.")
                        # Prevent overlap for same semester and non-prerequisite courses
                        for s1 in bc1_sections:
                            for s2 in bc2_sections:
                                model.Add(slot_vars[s1] != slot_vars[s2])
        # Ensure no instructor is assigned to more than one course at the same time
        instructor_sections = defaultdict(list)
        for section in all_sections:
            instr_id = instructor_assignments[section]# Skip TBA instructors (they can teach multiple courses at the same time)
            if instr_id == "TBA":
                continue
            instructor_sections[instr_id].append(section)

        for instr_id, sections in instructor_sections.items():
            # Separate lab sections and non-lab sections
            lab_sections = []
            non_lab_sections = []
            for s in sections:
                base_course = s.rsplit('_', 1)[0]
                if base_course.endswith('L'):
                    lab_sections.append(s)
                else:
                    non_lab_sections.append(s)

            # Enforce no overlap for non-lab sections
            n = len(non_lab_sections)
            if n > 1:
                for i in range(n):
                    for j in range(i + 1, n):
                        s1 = non_lab_sections[i]
                        s2 = non_lab_sections[j]
                        model.Add(slot_vars[s1] != slot_vars[s2])

            # Prevent lab sections from overlapping with non-lab courses
            for lab_section in lab_sections:
                for other_section in sections:
                    if lab_section == other_section:
                        continue
                    # Check if the other section is a lab
                    other_base = other_section.rsplit('_', 1)[0]
                    is_other_lab = other_base.endswith('L')
                    if not is_other_lab:
                        model.Add(slot_vars[lab_section] != slot_vars[other_section])
        # --- NEW CONSTRAINT: PREVENT LECTURE AND LAB OVERLAP ---
        # Identify lecture-lab pairs
        # Prevent lecture and lab overlaps (similar to regular scheduler):
        lecture_lab_pairs = defaultdict(list)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            if 'lab' in base_course.lower():  # Assuming lab courses have "lab" in their name
                lecture_base = base_course.replace('Lab', '')  # Adjust based on naming
                lecture_lab_pairs[lecture_base].append(section)
            else:
                lecture_lab_pairs[base_course].append(section)

        for base, sections in lecture_lab_pairs.items():
            lectures = [s for s in sections if 'lab' not in s.lower()]
            labs = [s for s in sections if 'lab' in s.lower()]
            for lecture in lectures:
                for lab in labs:
                    model.Add(slot_vars[lecture] != slot_vars[lab])

        # Add availability constraints for each course section
        for course_with_section in all_sections:
            instr_id = instructor_assignments[course_with_section]
            allowed = instructor_availability.get(instr_id, [])
            # If time is fixed, only allow that slot
            if course_with_section in fixed_times:
                allowed = [fixed_times[course_with_section]]
            else:
                # Convert time slots to indexes
                allowed = [time_slots.index(ts) for ts in allowed if ts in time_slots]
            if allowed:
                model.AddAllowedAssignments([slot_vars[course_with_section]], [[slot] for slot in allowed])
            else:
                print(f"No valid time slots available for instructor {instr_id}. Skipping constraint.")
        # Solve the model without an objective function
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        # Log solver status and statistics
        print(f"Status: {solver.StatusName(status)}")
        print(f"Number of variables: {len(slot_vars)}")
        print(f"Number of constraints: {model.Proto().constraints.__len__()}")
        # Check if a feasible solution was found
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = {}
            for section in all_sections:
                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(slot_vars[max(slot_vars, key=lambda s: solver.Value(slot_vars[s]))])
            schedule["completion_time"] = time_slots[max_slot]
            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: time_slots.index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]
            # Debugging: Log the generated schedule

            print(f"Generated Relaxed Schedule: {sorted_schedule}")

            # Function to filter courses with 'TBA' instructors
            def filter_tba_courses(schedule):
                filtered_schedule = {}

                for key, value in schedule.items():
                    # Only check course entries (skip completion_time or other metadata)
                    if isinstance(value, dict) and 'instructor' in value:
                        if value['instructor'] != 'TBA':
                            filtered_schedule[key] = value
                    else:
                        # Keep non-course keys like 'completion_time'
                        filtered_schedule[key] = value

                return filtered_schedule

            # Apply filtering
            filtered_schedule = filter_tba_courses(sorted_schedule)

            # Print result
            print(f"Generated Relaxed Schedule: {filtered_schedule}")

            save_result = save_schedule_to_database(
                filtered_schedule,
                school_code,
                campus_code,
                academic_year,
                semester
            )

            if not save_result:
                print("Warning: Failed to save schedule to database")
            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")
    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


def get_semester(course_code):
    """
    Extracts the semester information from a course code.
    Assumes the second numeric digit determines the semester:
        - < 5: First semester
        - >= 5: Second semester
    Ignores any trailing 'L' for lab courses.
    """
    # Remove trailing 'L' if present
    if course_code.endswith('L'):
        course_code = course_code[:-1]

    # Extract all numeric digits from the course code
    numeric_digits = [char for char in course_code if char.isdigit()]

    # Ensure there are at least two numeric digits
    if len(numeric_digits) < 2:
        raise ValueError(f"Invalid course code format: {course_code}")

    # The second numeric digit determines the semester
    second_digit = int(numeric_digits[1])  # Second numeric digit

    # Determine semester
    semester = "first" if second_digit < 5 else "second"

    # Debugging: Print the course code and its semester
    print(f"Course Code: {course_code}, Semester: {semester}")

    return semester

@app.route("/instructor-availability")
def instructor_availability():
    school_code = request.args.get("school_code")
    campus_code = request.args.get("campus_code")
    academic_year = request.args.get("academic_year")
    semester = request.args.get("semester")

    print(f"Fetching instructors for school_code: {school_code}, campus_code: {campus_code}")
    print(f"Academic Year: {academic_year}, Semester: {semester}")

    instructors = get_instructors_by_campus(campus_code, school_code , academic_year, semester)
    return render_template(
        "instructor_availability.html",
        instructors=instructors,
        time_slots=time_slots,
        school_code=school_code,
        campus_code=campus_code,
        academic_year=academic_year,
        semester=semester
    )


def get_instructors_for_course_selection(campus_code, school_code):
    """Fetch instructors from the database based on the selected campus and school."""
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print(f"Connecting to database to fetch instructors for campus_code: {campus_code} and school_code: {school_code}")
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()
        query = """
            SELECT facuser, fac_code, campusID
            FROM Instructor
            WHERE campusID = ? AND fac_code = ?
        """
        print(f"Executing query: {query} with params: {campus_code}, {school_code}")
        cursor.execute(query, campus_code, school_code)
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} instructors from the database.")
        cursor.close()
        connection.close()
        instructors_list = [
            {
                "identifier": row[0],
                "facuser": row[0],
                "fac_code": row[1],
                "campusID": row[2]
            }
            for row in rows
        ]
        return instructors_list
    except Exception as e:
        print(f"Error fetching instructors from database: {e}")
        return []


@app.route("/course-selection")
def course_selection():
    school_code = request.args.get("school_code")
    campus_code = request.args.get("campus_code")
    academic_year = request.args.get("academic_year")
    semester = request.args.get("semester")

    print(f"[DEBUG] Rendering course selection for school: {school_code}, campus: {campus_code}")

    # Fetch regular courses and instructors
    instructors = get_instructors_for_course_selection(campus_code, school_code)
    courses = get_courses_by_school(school_code)

    # Fetch selected service courses from session
    service_courses_json = session.get("selected_service_courses", [])
    service_courses = []

    for course_str in service_courses_json:
        import json
        course_data = json.loads(course_str)
        course_data["Title"] = f"{course_data['Title']} (Service)"  # Mark as service
        service_courses.append(course_data)

    # Merge regular + service courses
    all_courses = courses + service_courses

    # Fetch instructor availability
    try:
        response, status_code = fetch_instructor_availability_internal_for_course_selection(school_code, academic_year, semester)
        if "error" not in response:
            session["instructor_availability"] = response.get("instructor_availability", {})
        else:
            session["instructor_availability"] = {}
    except Exception as e:
        print(f"[ERROR] Fetching instructor availability: {e}")
        session["instructor_availability"] = {}

    instructor_availability = session.get("instructor_availability", {})

    return render_template(
        "course_selection.html",
        courses=all_courses,  # Includes both regular and service courses
        instructors=instructors,
        time_slots=time_slots,
        instructor_availability=instructor_availability,
        school_code=school_code,
        campus_code=campus_code,
        academic_year=academic_year,
        semester=semester
    )


def fetch_instructor_availability_internal(school_code, academic_year, semester, campus_code):
    try:
        # Define time slots for summer and regular semesters
        summer_time_slots = ['MWTTH 8:00-9:50', 'MWTTH 10:00-11:50', 'MWTTH 12:00-1:50']
        regular_time_slots = [
            "MW 8:00-9:15 AM", "MW 9:30-10:45 AM", "MW 11:00 AM-12:15 PM",
            "MW 12:30-1:45 PM", "MW 2:00-3:15 PM", "MW 3:30-4:45 PM",
            "MW 5:00-6:15 PM", "MW 6:30-8:45 PM",
            "TTh 8:00-9:15 AM", "TTh 9:30-11:45 AM", "TTh 11:00 AM-12:15 PM",
            "TTh 12:30-1:45 PM", "TTh 2:00-3:15 PM", "TTh 3:30-4:45 PM",
            "TTh 5:00-6:15 PM", "TTh 6:30-8:45 PM"
        ]
        # Select the appropriate time slots based on the semester
        time_slots = summer_time_slots if semester == "Summer" else regular_time_slots

        # Connect to the database
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print(f"[DEBUG] Connecting to database for school_code: {school_code}, academic_year: {academic_year}, semester: {semester}, campus_code: {campus_code}")
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Fetch instructor availability based on school_code, academic_year, semester, and campus_code
        query = """
            SELECT ia.facuser, ia.time_slot, i.title, i.fname, i.mname, i.lname
            FROM Instructor_Availability ia
            INNER JOIN Instructor i ON ia.facuser = i.facuser
            WHERE i.fac_code = ?
              AND ia.year = ?
              AND ia.semester = ?
              AND ia.campusID = ?
        """
        print(f"[DEBUG] Executing query: {query} with params: {school_code}, {academic_year}, {semester}, {campus_code}")
        cursor.execute(query, school_code, academic_year, semester, campus_code)
        rows = cursor.fetchall()
        print(f"[DEBUG] Fetched {len(rows)} rows from the database.")

        # Organize data into a dictionary
        instructor_availability = {}
        for row in rows:
            facuser = row.facuser
            time_slot = row.time_slot
            # Include only valid time slots for the semester
            if time_slot in time_slots:
                if facuser not in instructor_availability:
                    instructor_availability[facuser] = {
                        "time_slots": [],
                        "name": f"{row.title} {row.fname} {row.mname or ''} {row.lname}".strip()
                    }
                instructor_availability[facuser]["time_slots"].append(time_slot)

        # Add TBA with all time slots
        instructor_availability["TBA"] = {
            "time_slots": time_slots.copy(),
            "name": "To Be Announced"
        }
        print(f"[DEBUG] Organized instructor availability: {instructor_availability}")

        # Close the connection
        cursor.close()
        connection.close()
        return {"instructor_availability": instructor_availability}, 200
    except Exception as e:
        print(f"[ERROR] Error fetching instructor availability: {e}")
        return {"error": str(e)}, 500

def fetch_instructor_availability_internal_for_course_selection(school_code, academic_year, semester, campus_code):
    try:
        # Define time slots for summer and regular semesters
        summer_time_slots = ['MWTTH 8:00-9:50', 'MWTTH 10:00-11:50', 'MWTTH 12:00-1:50']
        regular_time_slots = [
            "MW 8:00-9:15 AM", "MW 9:30-10:45 AM", "MW 11:00 AM-12:15 PM",
            "MW 12:30-1:45 PM", "MW 2:00-3:15 PM", "MW 3:30-4:45 PM",
            "MW 5:00-6:15 PM", "MW 6:30-8:45 PM",
            "TTh 8:00-9:15 AM", "TTh 9:30-11:45 AM", "TTh 11:00 AM-12:15 PM",
            "TTh 12:30-1:45 PM", "TTh 2:00-3:15 PM", "TTh 3:30-4:45 PM",
            "TTh 5:00-6:15 PM", "TTh 6:30-8:45 PM"
        ]
        # Select the appropriate time slots based on the semester
        time_slots = summer_time_slots if semester == "Summer" else regular_time_slots

        # Connect to the database
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        print(f"[DEBUG] Connecting to database for school_code: {school_code}, academic_year: {academic_year}, semester: {semester}, campus_code: {campus_code}")
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Fetch instructor availability based on school_code, academic_year, semester, and campus_code
        query = """
            SELECT ia.facuser, ia.time_slot
            FROM Instructor_Availability ia
            INNER JOIN Instructor i ON ia.facuser = i.facuser
            WHERE i.fac_code = ?
              AND ia.year = ?
              AND ia.semester = ?
              AND ia.campusID = ?  -- Add this condition to filter by campusID
        """
        print(f"[DEBUG] Executing query: {query} with params: {school_code}, {academic_year}, {semester}, {campus_code}")
        cursor.execute(query, school_code, academic_year, semester, campus_code)
        rows = cursor.fetchall()
        print(f"[DEBUG] Fetched {len(rows)} rows from the database.")

        # Organize data into a dictionary
        instructor_availability = {}
        for row in rows:
            facuser = row.facuser
            time_slot = row.time_slot
            # Include only valid time slots for the semester
            if time_slot in time_slots:
                if facuser not in instructor_availability:
                    instructor_availability[facuser] = []
                instructor_availability[facuser].append(time_slot)
            if "TBA" not in instructor_availability:
                instructor_availability["TBA"] = time_slots.copy()
                print("[DEBUG] Added 'TBA' to instructor_availability with all time slots.")
        print(f"[DEBUG] Organized instructor availability: {instructor_availability}")

        # Close the connection
        cursor.close()
        connection.close()
        return {"instructor_availability": instructor_availability}, 200
    except Exception as e:
        print(f"[ERROR] Error fetching instructor availability: {e}")
        return {"error": str(e)}, 500

@app.route("/fetch_all_instructors")
def fetch_all_instructors():
    """Fetch all instructors from the database."""
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        query = """
            SELECT facuser, title, fname, mname, lname
            FROM Instructor
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        instructors_list = [
            {
                "facuser": row[0],
                "title": row[1],
                "fname": row[2],
                "mname": row[3],
                "lname": row[4]
            }
            for row in rows
        ]
        return jsonify(instructors_list), 200

    except Exception as e:
        print(f"Error fetching all instructors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/fetch_unavailable_instructors")
def fetch_unavailable_instructors():
    """Fetch instructors who are NOT currently available at the specified campus for the given year/semester."""
    try:
        school_code = request.args.get("school_code")
        campus_code = request.args.get("campus_code")
        year = request.args.get("year")
        semester = request.args.get("semester")


        if not school_code:
            return jsonify({"error": "Missing required parameter: school_code"}), 400
        if not campus_code:
            return jsonify({"error": "Missing required parameter: campus_code"}), 400
        if not year:
            return jsonify({"error": "Missing required parameter: year"}), 400
        if not semester:
            return jsonify({"error": "Missing required parameter: semester"}), 400

        # Step 1: Get the list of instructors already available at the campus (same as get_instructors_by_campus)
        current_instructors = get_instructors_by_campus(campus_code, school_code, year, semester)
        current_facusers = [instructor['facuser'] for instructor in current_instructors]

        print(f"Excluding instructors: {current_facusers}")

        # Step 2: Create DB connection
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Step 3: Fetch all active instructors in the school EXCEPT those already included above
        if current_facusers:
            placeholders = ','.join('?' * len(current_facusers))
            query = f"""
                SELECT facuser, title, fname, mname, lname
                FROM Instructor
                WHERE fac_code = ? AND Active = 1 AND facuser NOT IN ({placeholders})
            """
            params = [school_code] + current_facusers
        else:
            query = """
                SELECT facuser, title, fname, mname, lname
                FROM Instructor
                WHERE fac_code = ? AND Active = 1
            """
            params = [school_code]

        cursor.execute(query, params)
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        # Build response
        unavailable_list = [
            {
                "facuser": row[0],
                "title": row[1],
                "fname": row[2],
                "mname": row[3],
                "lname": row[4]
            }
            for row in rows
        ]

        return jsonify(unavailable_list), 200

    except Exception as e:
        print(f"Error fetching unavailable instructors: {e}")
        return jsonify({"error": str(e)}), 500

"""@app.route("/delete_availability", methods=["POST"])
def delete_availability():
    try:
        # Connect to the database
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Delete all rows from the Instructor_Availability table
        delete_query = "DELETE FROM Instructor_Availability"
        cursor.execute(delete_query)

        # Commit the transaction
        connection.commit()
        print("All instructor availability data deleted successfully.")

        # Close the connection
        cursor.close()
        connection.close()

        return jsonify({"message": "All instructor availability data deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting availability: {e}")
        return jsonify({"error": str(e)}), 500"""


@app.route("/fetch_instructor_availability", methods=["GET"])
def fetch_instructor_availability():
    try:
        # Retrieve query parameters
        school_code = request.args.get("school_code")
        academic_year = request.args.get("academic_year")  # Retrieve academic_year
        semester = request.args.get("semester")  # Retrieve semester
        campus = request.args.get("campus_code")

        # Debugging: Log the retrieved parameters
        print(f"[DEBUG] Inside /fetch_instructor_availability endpoint")
        print(
            f"[DEBUG] Retrieved query parameters: school_code={school_code}, academic_year={academic_year}, semester={semester}")

        # Call the existing fetch_instructor_availability_internal function
        response, status_code = fetch_instructor_availability_internal(
            school_code, academic_year, semester , campus
        )

        # Debugging: Log the response from the internal function
        print(f"[DEBUG] Response from fetch_instructor_availability_internal: {response}")

        # Return the response as JSON
        if "error" in response:
            return jsonify({"error": response["error"]}), status_code
        else:
            return jsonify(response), status_code
    except Exception as e:
        print(f"[ERROR] Error fetching instructor availability: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/save_availability", methods=["POST"])
def save_instructor_availability():
    try:
        # Extract form data
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")
        academic_year = request.form.get("academic_year")
        semester = request.form.get("semester")

        # Validate required fields
        if not school_code or not campus_code or not academic_year or not semester:
            return jsonify({"error": "School code, campus code, academic year, and semester are required."}), 400

        # Connect to the database
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        try:
            connection = pyodbc.connect(conn_string)
            print("Database connection successful!")
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            return jsonify({"error": "Database connection failed."}), 500

        # Delete previous records for the same semester, year, and campus
        try:
            with connection.cursor() as cursor:
                delete_query = """
                    DELETE FROM Instructor_Availability 
                    WHERE year = ? AND semester = ? AND campusID = ?
                """
                cursor.execute(delete_query, (academic_year, semester, campus_code))
                connection.commit()
                print(f"Deleted previous availability records for {academic_year} {semester} {campus_code}")
        except Exception as e:
            print(f"Error deleting previous records: {e}")
            return jsonify({"error": "Failed to delete previous records."}), 500

        # Define time slots for MW, TTh, and Summer
        mw_time_slots = [
            "MW 8:00-9:15 AM", "MW 9:30-10:45 AM", "MW 11:00 AM-12:15 PM",
            "MW 12:30-1:45 PM", "MW 2:00-3:15 PM", "MW 3:30-4:45 PM",
            "MW 5:00-6:15 PM", "MW 6:30-8:45 PM"
        ]

        tth_time_slots = [
            "TTh 8:00-9:15 AM", "TTh 9:30-10:45 AM", "TTh 11:00 AM-12:15 PM",
            "TTh 12:30-1:45 PM", "TTh 2:00-3:15 PM", "TTh 3:30-4:45 PM",
            "TTh 5:00-6:15 PM", "TTh 6:30-8:45 PM"
        ]

        summer_time_slots = ['MWTTH 8:00-9:50', 'MWTTH 10:00-11:50', 'MWTTH 12:00-1:50']

        # Parse and save instructor availability
        instructor_availability = {}
        for key in request.form.keys():
            if key.startswith("availability_"):
                facuser = key.split("availability_", 1)[1]  # Extract facuser
                print(f"Extracted facuser: {facuser}")

                # Validate facuser exists in the Instructor table
                try:
                    with connection.cursor() as cursor:
                        check_query = "SELECT COUNT(*) FROM Instructor WHERE facuser = ?"
                        cursor.execute(check_query, facuser)
                        count = cursor.fetchone()[0]
                        if count == 0:
                            print(f"Invalid facuser: {facuser}. Skipping...")
                            continue  # Skip invalid facuser
                except Exception as e:
                    print(f"Error validating facuser: {e}")
                    return jsonify({"error": "Database query failed."}), 500

                # Parse availability slots
                availability_slots = request.form.getlist(key)
                for av in availability_slots:
                    try:
                        day, slot_index = av.split("_")
                        day = int(day)  # Convert day to integer
                        slot_index = int(slot_index)  # Convert slot index to integer

                        # Determine the time slot based on the semester
                        if semester == "Summer":
                            if day != 0:  # Summer only has one day group (MWTH)
                                print(f"Invalid day for summer: {day}. Skipping...")
                                continue
                            time_slot = summer_time_slots[slot_index]
                        else:
                            # Regular semester (MW or TTh)
                            if day == 0:  # MW
                                time_slot = mw_time_slots[slot_index]
                            elif day == 1:  # TTh
                                time_slot = tth_time_slots[slot_index]
                            else:
                                print(f"Invalid day: {day}. Skipping...")
                                continue

                        # Check if the record already exists in the database
                        with connection.cursor() as cursor:
                            check_duplicate_query = """
                                SELECT COUNT(*) 
                                FROM Instructor_Availability 
                                WHERE facuser = ? AND campusID = ? AND time_slot = ? AND year = ? AND semester = ?
                            """
                            cursor.execute(
                                check_duplicate_query,
                                facuser, campus_code, time_slot, academic_year, semester
                            )
                            duplicate_count = cursor.fetchone()[0]

                            # Insert only if the record does not exist
                            if duplicate_count == 0:
                                insert_query = """
                                    INSERT INTO Instructor_Availability (facuser, campusID, time_slot, year, semester)
                                    VALUES (?, ?, ?, ?, ?)
                                """
                                cursor.execute(
                                    insert_query,
                                    facuser, campus_code, time_slot, academic_year, semester
                                )
                                connection.commit()
                                print(f"Inserted new record: facuser={facuser}, campusID={campus_code}, time_slot={time_slot}, year={academic_year}, semester={semester}")
                            else:
                                print(f"Duplicate record found, skipping: facuser={facuser}, campusID={campus_code}, time_slot={time_slot}, year={academic_year}, semester={semester}")

                    except Exception as e:
                        print(f"Error processing availability: {e}")
                        continue

        # Close the connection
        connection.close()

        # Redirect to course selection page
        return redirect(url_for(
            "course_selection",
            school_code=school_code,
            campus_code=campus_code,
            academic_year=academic_year,
            semester=semester
        ))

    except Exception as e:
        print(f"Error saving availability: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/save_instructor', methods=['POST'])
def save_instructor():
    facuser = request.form.get('facuser')
    title = request.form.get('title')
    fname = request.form.get('fname')
    mname = request.form.get('mname')
    lname = request.form.get('lname')
    accountEmail = request.form.get('accountEmail') or None
    division = request.form.get('division')
    fac_code = request.form.get('fac_code')
    campusID = request.form.get('campusID')
    active = request.form.get('active')  # 'Yes' or 'No'
    active_bit = 1 if active == "Yes" else 0
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = """
        INSERT INTO instructor (facuser, title, fname, mname, lname, accountEmail, Division, fac_code, campusID, Active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (facuser, title, fname, mname, lname, accountEmail, division, fac_code, campusID, active_bit))
        connection.commit()
        return jsonify({}), 200
    except Exception as e:
        print("Error saving instructor:", e)
        return jsonify({"error": "Failed to save instructor"}), 500
    finally:
        connection.close()


@app.route("/save_course", methods=["POST"])
def save_course():
    """
    Save a new course to the database.
    Automatically determines course_year based on course code suffix.
    """
    try:
        # Get form data
        course_code = request.form.get("course_code")
        course_title = request.form.get("course_title")
        credits = request.form.get("credits")
        capcity = request.form.get("capcity")
        level = request.form.get("level")
        faculty_code = request.form.get("faculty_code")

        # Validate course code format
        if not course_code or len(course_code) < 3:
            return jsonify({"error": "Course code must be at least 3 characters long"}), 400

        # Handle lab courses (ends with 'L')
        is_lab = course_code.endswith('L')

        if is_lab:
            # Remove 'L' and take the previous 3 digits
            suffix = course_code[-4:-1]
        else:
            # Take last 3 characters as usual
            suffix = course_code[-3:]

        # Validate numeric suffix
        if not suffix.isdigit():
            return jsonify({"error": "Course code must have 3 digits before the 'L', e.g., CSCI300L"}), 400

        course_number = int(suffix)

        # Map course number to course_year
        if 100 <= course_number < 200:
            course_year = "Freshman Course"
        elif 200 <= course_number < 300:
            course_year = "First-year course"
        elif 300 <= course_number < 400:
            course_year = "Second-year course"
        elif 400 <= course_number < 500:
            course_year = "Third-year course"
        elif 500 <= course_number < 600:
            course_year = "Fourth-year course"
        elif 600 <= course_number < 700:
            course_year = "Fifth-year course"
        else:
            course_year = "Advanced or Special Course"

        # If it's a lab course, append " (Lab)"
        if is_lab:
            course_year += " (Lab)"

        # Database connection
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Check if course code already exists
        check_query = "SELECT COUNT(*) FROM Course WHERE Code = ?"
        cursor.execute(check_query, (course_code,))
        count = cursor.fetchone()[0]

        if count > 0:
            cursor.close()
            connection.close()
            return jsonify({"error": "Course code already exists. Please choose another code."}), 400

        # Insert the course
        insert_query = """
            INSERT INTO Course (Code, Title, Credits, Capcity, Level, fac_code, course_year)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (
            course_code,
            course_title,
            credits,
            capcity,
            level,
            faculty_code,
            course_year
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("insert_course"))

    except Exception as e:
        print(f"Error saving course: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_instructor', methods=['POST'])
def update_instructor():
    facuser = request.form.get('facuser')
    title = request.form.get('title')
    fname = request.form.get('fname')
    mname = request.form.get('mname')
    lname = request.form.get('lname')
    accountEmail = request.form.get('accountEmail') or None
    division = request.form.get('division')
    fac_code = request.form.get('fac_code')
    campusID = request.form.get('campusID')
    active = request.form.get('active')  # 'Yes' or 'No'
    active_bit = 1 if active == "Yes" else 0

    if not facuser:
        return jsonify({"error": "Faculty user is required"}), 400

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()

        # Check if instructor exists
        check_query = "SELECT COUNT(*) FROM instructor WHERE facuser = ?"
        cursor.execute(check_query, (facuser,))
        count = cursor.fetchone()[0]

        if count == 0:
            return jsonify({"error": "Instructor not found"}), 404

        # Update instructor
        query = """
        UPDATE instructor 
        SET title = ?, fname = ?, mname = ?, lname = ?, accountEmail = ?, 
            Division = ?, fac_code = ?, campusID = ?, Active = ?
        WHERE facuser = ?
        """
        cursor.execute(query, (title, fname, mname, lname, accountEmail, division,
                              fac_code, campusID, active_bit, facuser))
        connection.commit()
        return jsonify({"message": "Instructor updated successfully"}), 200
    except Exception as e:
        print("Error updating instructor:", e)
        return jsonify({"error": f"Failed to update instructor: {str(e)}"}), 500
    finally:
        connection.close()
@app.route("/index")
def index():
        """
        Render the index page.
        """
        return render_template("index.html")

@app.route("/insert_course")
def insert_course():
        """
        Render the insert course page.
        """
        return render_template("insert_course.html")

@app.route("/edit_course")
def edit_course():
        """
        Render the edit course page.
        """
        return render_template("edit_course.html")


@app.route('/get_faculties_by_school')
def get_faculties_by_school():
    schl_code = request.args.get('schlCode')

    if not schl_code:
        return jsonify([])

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = "SELECT faccode FROM Faculty WHERE schlCode = ? ORDER BY faccode ASC"
        cursor.execute(query, schl_code)
        rows = cursor.fetchall()
        faculties = [row[0] for row in rows]
        return jsonify(faculties)
    except Exception as e:
        print(f"Error fetching faculty codes: {e}")
        return jsonify([])
    finally:
        connection.close()

def get_schools_from_db():
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = "SELECT DISTINCT schlCode FROM Faculty ORDER BY schlCode ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        schools = [{"school_code": row[0]} for row in rows]
        return schools
    except Exception as e:
        print(f"Error fetching schools: {e}")
        return []
    finally:
        connection.close()

@app.route('/insert_instructor')
def insert_instructor():
    schools = get_schools_from_db()
    campuses = get_campuses_from_db()  # assuming you already have this
    return render_template('insert_instructor.html', schools=schools, campuses=campuses)

@app.route('/check_facuser', methods=['GET'])
def check_facuser():
    facuser = request.args.get('facuser')
    if not facuser:
        return jsonify({"exists": False})

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = "SELECT COUNT(*) FROM instructor WHERE facuser = ?"
        cursor.execute(query, facuser)
        count = cursor.fetchone()[0]
        return jsonify({"exists": count > 0})
    except Exception as e:
        print("Error checking facuser:", e)
        return jsonify({"exists": False})
    finally:
        connection.close()

@app.route('/check_course_code', methods=['GET'])
def check_course_code():
    course_code = request.args.get('course_code')
    if not course_code:
        return jsonify({"exists": False})

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = "SELECT COUNT(*) FROM Course WHERE Code = ?"
        cursor.execute(query, course_code)
        count = cursor.fetchone()[0]
        return jsonify({"exists": count > 0})
    except Exception as e:
        print("Error checking course code:", e)
        return jsonify({"exists": False})
    finally:
        connection.close()

@app.route('/update_course', methods=['POST'])
def update_course():
    try:
        # Get form data
        course_code = request.form.get("course_code")
        course_title = request.form.get("course_title")
        credits = request.form.get("credits")
        capcity = request.form.get("capcity")
        level = request.form.get("level")
        faculty_code = request.form.get("faculty_code")

        # Validate input
        if not course_code:
            return jsonify({"error": "Course code is required"}), 400

        # Database connection
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Check if course exists
        check_query = "SELECT COUNT(*) FROM Course WHERE Code = ?"
        cursor.execute(check_query, (course_code,))
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.close()
            connection.close()
            return jsonify({"error": "Course not found"}), 404

        # Update the course
        update_query = """
            UPDATE Course 
            SET Title = ?, Credits = ?, Capcity = ?, Level = ?, fac_code = ?
            WHERE Code = ?
        """
        cursor.execute(update_query, (
            course_title,
            credits,
            capcity,
            level,
            faculty_code,
            course_code
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Course updated successfully"}), 200
    except Exception as e:
        print(f"Error updating course: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_course_details', methods=['GET'])
def get_course_details():
    course_code = request.args.get('course_code')
    if not course_code:
        return jsonify({"error": "Course code is required"}), 400

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = """
        SELECT Code, Title, Credits, Capcity, Level, fac_code, course_year
        FROM Course 
        WHERE Code = ?
        """
        cursor.execute(query, course_code)
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Course not found"}), 404

        course = {
            "course_code": row[0],
            "course_title": row[1],
            "credits": row[2],
            "capcity": row[3],
            "level": row[4],
            "faculty_code": row[5],
            "course_year": row[6] if row[6] else ""
        }

        return jsonify(course), 200
    except Exception as e:
        print("Error fetching course details:", e)
        return jsonify({"error": "Failed to fetch course details"}), 500
    finally:
        connection.close()


@app.route("/fetch_all_courses")
def fetch_all_courses():
    """Fetch all courses from the database."""
    try:
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        query = """
            SELECT Code, Title
            FROM Course
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        courses_list = [
            {
                "course_code": row[0],
                "course_title": row[1]
            }
            for row in rows
        ]
        return jsonify(courses_list), 200

    except Exception as e:
        print(f"Error fetching all courses: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/edit_instructor')
def edit_instructor():
    campuses = get_campuses_from_db()
    return render_template('edit_instructor.html', campuses=campuses)


@app.route('/get_instructor_details', methods=['GET'])
def get_instructor_details():
    facuser = request.args.get('facuser')
    if not facuser:
        return jsonify({"error": "Faculty user is required"}), 400

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = """
        SELECT facuser, title, fname, mname, lname, accountEmail, Division, fac_code, campusID, Active
        FROM instructor 
        WHERE facuser = ?
        """
        cursor.execute(query, facuser)
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Instructor not found"}), 404

        instructor = {
            "facuser": row[0],
            "title": row[1],
            "fname": row[2],
            "mname": row[3],
            "lname": row[4],
            "accountEmail": row[5] if row[5] else "",
            "division": row[6] if row[6] else "",
            "fac_code": row[7],
            "campusID": row[8],
            "active": "Yes" if row[9] == 1 else "No"
        }

        return jsonify(instructor), 200
    except Exception as e:
        print("Error fetching instructor details:", e)
        return jsonify({"error": "Failed to fetch instructor details"}), 500
    finally:
        connection.close()

@app.route('/get_faculties')
def get_faculties():
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        query = "SELECT DISTINCT faccode FROM Faculty ORDER BY faccode ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        faculties = [row[0] for row in rows]
        return jsonify(faculties)
    except Exception as e:
        print("Error fetching faculty codes:", e)
        return jsonify([])
    finally:
        connection.close()


def check_semester_exists(cursor, year, semester):
    """
    Check if a Year and Semester combination exists in the Semester table.

    Args:
        cursor: Database cursor
        year (str): The academic year
        semester (str): The semester (Fall, Spring, Summer)

    Returns:
        bool: True if the combination exists, False otherwise
    """
    query = """
    SELECT COUNT(*) FROM Semester 
    WHERE Year = ? AND Season = ?
    """
    cursor.execute(query, (year, semester))
    count = cursor.fetchone()[0]
    return count > 0

def create_semester_entry(cursor, connection, year, semester):
    """
    Create a new entry in the Semester table.

    Args:
        cursor: Database cursor
        connection: Database connection
        year (str): The academic year
        semester (str): The semester (Fall, Spring, Summer)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        query = """
        INSERT INTO Semester (Year, Season) 
        VALUES (?, ?)
        """
        cursor.execute(query, (year, semester))
        connection.commit()
        print(f"Created new Semester entry: Year='{year}', Season='{semester}'")
        return True
    except Exception as e:
        print(f"Error creating Semester entry: {e}")
        return False

def save_schedule_to_database(schedule, school_code, campus_code, academic_year, semester):
    """
    Save the generated schedule to the Schedule table in the database.
    If records exist for the same semester, year, and fac_code, delete them first.

    Args:
        schedule (dict): The generated schedule data
        school_code (str): The faculty code
        campus_code (str): The campus code
        academic_year (str): The academic year
        semester (str): The semester (Fall, Spring, Summer)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create the connection string
        conn_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']};"
        )

        # Establish the database connection
        connection = pyodbc.connect(conn_string)
        cursor = connection.cursor()

        # Check if the Year and Semester combination exists in the Semester table
        if not check_semester_exists(cursor, academic_year, semester):
            print(f"The combination of Year '{academic_year}' and Semester '{semester}' does not exist in the Semester table.")
            print("Attempting to create a new Semester entry...")

            # Try to create a new entry in the Semester table
            if not create_semester_entry(cursor, connection, academic_year, semester):
                print("Failed to create a new Semester entry. Cannot proceed with saving the schedule.")
                cursor.close()
                connection.close()
                return False

            print("Successfully created a new Semester entry.")

        # Check if records exist for the same semester, year, and fac_code
        check_query = """
        SELECT COUNT(*) FROM Schedule 
        WHERE Year = ? AND Semester = ? AND fac_code = ? AND Campus = ?
        """
        cursor.execute(check_query, (academic_year, semester, school_code ,campus_code))
        count = cursor.fetchone()[0]

        # If records exist, delete them
        if count > 0:
            delete_query = """
            DELETE FROM Schedule 
            WHERE Year = ? AND Semester = ? AND fac_code = ? AND Campus = ?
            """
            cursor.execute(delete_query, (academic_year, semester, school_code , campus_code))
            print(f"Deleted {count} existing schedule records for {academic_year} {semester} {school_code} {campus_code}.")

        # Insert new records
        insert_query = """
        INSERT INTO Schedule (
            CourseNumber, Code, Section, FACUSER, Room, 
            STIME, ETIME, M, T, W, TH, F, S, 
            Campus, University, AllowCross, SchedulingType, 
            BypassPayroll, Capacity, Year, Semester, fac_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Process each section in the schedule
        row_number = 1
        for section, details in schedule.items():
            # Skip the completion_time entry
            if section == "completion_time":
                continue

            # Parse section into code and section letter
            code, section_letter = section.split("_")

            # Get instructor
            instructor = details.get("instructor", "TBA")

            # Parse time
            time_str = details.get("time", "")

            # Default values
            stime = ""
            etime = ""
            m, t, w, th, f, s = 0, 0, 0, 0, 0, 0

            # Parse time based on semester
            if semester.lower() == "summer":
                # Summer time format: "MWTTH 8:00-9:50"
                if time_str:
                    # Extract days
                    days = time_str.split(" ")[0]
                    if "M" in days: m = 1
                    if "T" in days: t = 1
                    if "W" in days: w = 1
                    if "TH" in days: th = 1
                    if "F" in days: f = 1
                    if "S" in days: s = 1

                    # Extract time
                    time_parts = time_str.split(" ")[1].split("-")
                    stime = time_parts[0]  # e.g., '8:00'
                    etime = time_parts[1]  # e.g., '9:50'

            else:
                # Regular semester format: "MW 8:00-9:15 AM"
                if time_str:
                    # Extract days
                    days = time_str.split(" ")[0]
                    if "M" in days: m = 1
                    if "T" in days and "TH" not in days: t = 1
                    if "W" in days: w = 1
                    if "TH" in days: th = 1
                    if "F" in days: f = 1
                    if "S" in days: s = 1

                    # Extract time range
                    time_range = time_str.split(" ", 1)[1].strip()  # e.g., "8:00-9:15 AM"
                    time_part, ampm = time_range.rsplit(" ", 1)  # split into time and AM/PM
                    start_time, end_time = time_part.split("-")  # split into start and end

                    stime = start_time.strip()  # now it's "8:00"
                    etime = end_time.strip()  # now it's "9:15"

            # Insert the record
            cursor.execute(
                insert_query,
                (
                    row_number,  # CourseNumber
                    code,        # Code
                    section_letter,  # Section
                    instructor,  # FACUSER
                    "TBD",       # Room (default to TBD)
                    stime,       # STIME
                    etime,       # ETIME
                    m, t, w, th, f, s,  # Days of the week
                    campus_code, # Campus
                    1,           # University (default to 1)
                    0,           # AllowCross (default to 0)
                    "Normal",    # SchedulingType (default to Normal)
                    0,           # BypassPayroll (default to 0)
                    30,          # Capacity (default to 30)
                    academic_year,  # Year
                    semester,    # Semester
                    school_code  # fac_code
                )
            )

            row_number += 1

        # Commit the transaction
        connection.commit()
        print(f"Successfully saved {row_number-1} schedule records to the database")

        # Close the connection
        cursor.close()
        connection.close()

        return True

    except Exception as e:
        print(f"Error saving schedule to database: {e}")
        return False

if __name__ == "__main__":
    print("Starting Flask application in debug mode.")
    app.run(debug=True)