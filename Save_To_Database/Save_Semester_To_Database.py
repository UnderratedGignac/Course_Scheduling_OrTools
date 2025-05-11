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
