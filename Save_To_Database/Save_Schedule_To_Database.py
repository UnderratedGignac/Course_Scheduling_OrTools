import pyodbc

from Check_Data.Check_Semester_existance import check_semester_exists
from Save_To_Database.Save_Semester_To_Database import create_semester_entry
from config import DB_CONFIG


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
