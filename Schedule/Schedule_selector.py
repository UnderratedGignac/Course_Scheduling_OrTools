from flask import session, jsonify, request

from Get_Data_From_Database.Get_Instructor_From_database import \
    fetch_instructor_availability_internal_for_course_selection
from Schedule.Regular_Scheduling import generate_relaxed_schedule
from Schedule.Summer_Scheduling import generate_summer_schedule


def schedule_handler():
    try:
        # Retrieve session data
        instructor_availability = session.get("instructor_availability", {})
        if not instructor_availability:
            # Re-fetch instructor availability if missing
            school_code = request.form.get("school_code")
            campus_code = request.form.get("campus_code")  # Include campus_code
            academic_year = request.form.get("academic_year")
            semester = request.form.get("semester")
            if not school_code or not campus_code or not academic_year or not semester:
                return jsonify({"error": "Required parameters are missing."}), 400

            # Fetch instructor availability based on school_code, campus_code, academic_year, and semester
            response, status_code = fetch_instructor_availability_internal_for_course_selection(
                school_code, academic_year, semester, campus_code  # Pass campus_code
            )
            if "error" in response:
                return jsonify({"error": response["error"]}), status_code

            # Update session with the fetched instructor availability
            instructor_availability = response.get("instructor_availability", {})
            session["instructor_availability"] = instructor_availability

        # Debugging: Log the instructor availability
        print(f"[DEBUG] Instructor availability retrieved: {instructor_availability}")

        # Continue with scheduling logic...
        semester = request.form.get("semester")
        print(semester)

        # Validate semester
        if not semester:
            return jsonify({"error": "Semester information is missing."}), 400

        # Redirect to the appropriate function based on the semester
        if semester.lower() == "summer":
            return generate_summer_schedule()
        else:
            return generate_relaxed_schedule()

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500