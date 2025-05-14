import json

from flask import Flask, render_template, redirect, url_for, request, jsonify, session, send_file
import pyodbc  # For Microsoft SQL Server connection
from ortools.sat.python import cp_model  # For constraint programming
from collections import defaultdict  # Add this import at the top

from Get_Data_From_Database.Get_Faculty_From_database import get_Faculty_from_db
from Get_Data_From_Database.Get_Instructor_From_database import \
    fetch_instructor_availability_internal_for_course_selection, get_instructors_by_campus, \
    fetch_instructor_availability_internal, get_instructors_for_course_selection
from Get_Data_From_Database.Get_Schools_From_Database import get_schools_from_db
from Get_Data_From_Database.Get_campus_from_database import get_campuses_from_db
from Get_Data_From_Database.Get_course_from_database import get_service_courses, get_courses_by_school
from Schedule.Regular_Scheduling import generate_relaxed_schedule
from Schedule.Schedule_selector import schedule_handler
from Schedule.Summer_Scheduling import generate_summer_schedule
from config import app, DB_CONFIG
from time_slots import time_slots


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
    academic_years = [f"{current_year-1}-{current_year}",f"{current_year}-{next_year}", f"{next_year}-{next_year + 1}"]

    # Define semesters
    semesters = ["Fall", "Spring", "Summer"]

    return render_template(
        "school_selection.html",
        schools=schools,
        campuses=campuses,
        academic_years=academic_years,  # Pass academic years to the template
        semesters=semesters  # Pass semesters to the template
    )

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

    # Redirect to the next page, passing all selected values
    return redirect(url_for(
        "instructor_availability",
        school_code=school_code,
        campus_code=campus_code,
        academic_year=academic_year,
        semester=semester
    ))

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

@app.route('/edit_instructor')
def edit_instructor():
    campuses = get_campuses_from_db()
    return render_template('edit_instructor.html', campuses=campuses)

@app.route('/get_instructor_details', methods=['GET'])
def get_instructor_detail():
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

@app.route('/save_schedule', methods=['POST'])
def save_schedule():
    data = request.json
    headers = data.get('headers')
    schedule_data = data.get('scheduleData')

    # Get metadata from request
    academic_year = data.get('academicYear')  # Maps to Year column
    semester = data.get('semester')  # Maps to Semester column
    campus_code = data.get('campusCode')  # Maps to Campus column (convert to int)
    school_code = data.get('schoolCode')  # Optional: if needed for filtering

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

        # Convert campus_code to integer (if valid)
        campus_int = int(campus_code) if campus_code and campus_code.isdigit() else 0

        # 🔥 DELETE OLD RECORDS FOR THE SAME TERM/CAMPUS FIRST
        cursor.execute("""
                       DELETE
                       FROM schedule
                       WHERE Campus = ?
                                 AND Year = ?
                         AND Semester = ?
                           And fac_code = ?
                       """, (campus_int, academic_year, semester, school_code))

        # Insert new schedule data
        query = """
                INSERT INTO schedule (CourseNumber, Code, Section, FACUSER, Room, \
                                      STIME, ETIME, M, T, W, TH, F, S, Campus, University, \
                                      AllowCross, SchedulingType, BypassPayroll, Capacity, \
                                      Year, Semester, fac_code) \
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                """

        for idx, row in enumerate(schedule_data):
            # Map row data to parameters
            params = (
                idx + 1,  # CourseNumber (row index)
                row[1],  # Code
                row[2],  # Section
                row[3],  # FACUSER (instructor)
                row[4],  # Room
                row[5],  # STIME
                row[6],  # ETIME
                int(row[7]) if row[7] else 0,  # M
                int(row[8]) if row[8] else 0,  # T
                int(row[9]) if row[9] else 0,  # W
                int(row[10]) if row[10] else 0,  # TH
                int(row[11]) if row[11] else 0,  # F
                int(row[12]) if row[12] else 0,  # S
                campus_int,  # Campus (converted to int)
                1,  # University (default value)
                0,  # AllowCross (default value)
                'Normal',  # SchedulingType (default value)
                0,  # BypassPayroll (default value)
                30,  # Capacity (default value)
                academic_year,  # Year
                semester,  # Semester
                school_code  # fac_code (nullable)
            )
            cursor.execute(query, params)

        connection.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        print("Error saving schedule:", e)
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    app.run(debug=True)