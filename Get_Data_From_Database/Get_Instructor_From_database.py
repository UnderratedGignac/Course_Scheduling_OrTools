import pyodbc
from flask import jsonify, request

from config import DB_CONFIG


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

        TBA_instructor = "TBA_" + school_code

        instructor_availability[TBA_instructor] = {
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
        tba_instructor = "TBA_" + school_code
        print (tba_instructor)
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
            if tba_instructor not in instructor_availability:
                instructor_availability[tba_instructor] = time_slots.copy()
                print("[DEBUG] Added 'TBA' to instructor_availability with all time slots.")
        print(f"[DEBUG] Organized instructor availability: {instructor_availability}")

        # Close the connection
        cursor.close()
        connection.close()
        return {"instructor_availability": instructor_availability}, 200
    except Exception as e:
        print(f"[ERROR] Error fetching instructor availability: {e}")
        return {"error": str(e)}, 500


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
