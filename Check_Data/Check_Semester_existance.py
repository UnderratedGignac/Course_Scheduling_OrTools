
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
