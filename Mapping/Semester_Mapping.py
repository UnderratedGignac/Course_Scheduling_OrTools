
def get_semester(course_code):
    """
    Extracts the semester information from a course code.
    Assumes the second numeric digit determines the semester:
        - < 5: First semester
        - >= 5: Second semester
    Ignores any trailing 'L' for lab courses.
    """
    # Remove trailing 'L' if present
    if course_code.endswith('L'):
        course_code = course_code[:-1]

    # Extract all numeric digits from the course code
    numeric_digits = [char for char in course_code if char.isdigit()]

    # Ensure there are at least two numeric digits
    if len(numeric_digits) < 2:
        raise ValueError(f"Invalid course code format: {course_code}")

    # The second numeric digit determines the semester
    second_digit = int(numeric_digits[1])  # Second numeric digit

    # Determine semester
    semester = "first" if second_digit < 5 else "second"

    # Debugging: Print the course code and its semester
    print(f"Course Code: {course_code}, Semester: {semester}")

    return semester
