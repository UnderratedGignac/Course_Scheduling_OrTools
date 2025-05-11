import pyodbc

from config import DB_CONFIG


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