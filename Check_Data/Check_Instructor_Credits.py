def validate_instructor_credits(instructor_assignments, max_credits=21):
    """
    Validate that no instructor is assigned more than the allowed maximum credits.

    :param instructor_assignments: Dictionary mapping instructor IDs to their assigned courses and credits.
    :param max_credits: Maximum allowed credits per instructor (default 21).
    :return: True if valid, False otherwise.
    """
    for instructor_id, assignments in instructor_assignments.items():
        total_credits = sum(assignment['credits'] for assignment in assignments)
        if total_credits > max_credits:
            print(f"Instructor {instructor_id} has {total_credits} credits (max {max_credits} allowed).")
            return False
    return True

