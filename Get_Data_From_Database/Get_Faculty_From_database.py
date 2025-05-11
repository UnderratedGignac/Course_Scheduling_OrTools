import pyodbc
from flask import request, jsonify

from config import DB_CONFIG


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

