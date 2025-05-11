import pyodbc

from config import DB_CONFIG


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
