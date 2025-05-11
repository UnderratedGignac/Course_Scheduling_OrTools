from collections import defaultdict

import pyodbc

from config import DB_CONFIG


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

