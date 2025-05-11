import pyodbc
from flask import request, jsonify

# Database configuration
from config import DB_CONFIG


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
