from flask import request, jsonify, session
from ortools.sat.python import cp_model

from Get_Data_From_Database.Get_Instructor_From_database import get_instructors_by_school
from Mapping.Semester_Mapping import get_semester
from Save_To_Database.Save_Schedule_To_Database import save_schedule_to_database


def generate_summer_schedule():
    try:
        # Define time slots for regular courses and lab courses
        regular_time_slots = ['MWTTH 8:00-9:50', 'MWTTH 10:00-11:50', 'MWTTH 12:00-1:50']
        lab_time_slots = ['MWTH 8:00-9:50', 'MWTH 10:00-11:50', 'MWTH 12:00-1:50']

        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))

        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}
        course_semesters = {}  # FIXED: Added initialization here

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")
        academic_year = request.form.get("academic_year")

        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400

        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400

        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        if not instructor_availability:
            return jsonify({"error": "Instructor availability data is missing."}), 400

        # Debugging: Log the instructor availability data
        print(f"Instructor Availability Data: {instructor_availability}")

        # Process selected courses
        all_sections = []
        selected_courses = request.form.getlist("courses")
        for course_with_section in selected_courses:
            base_course, section_letter = course_with_section.rsplit("_", 1)
            num_students = int(request.form[f"students_{course_with_section}"])
            instructor_key = f"instructor_{course_with_section}"
            instructor = request.form.get(instructor_key, "TBA")  # Default to TBA
            instructor_assignments[course_with_section] = instructor
            year = int(request.form[f"year_{course_with_section}"])
            semester = get_semester(base_course)
            course_semesters[course_with_section] = semester  # This line now works

            # Check if the course is a lab course based on its title
            is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
            time_slots = lab_time_slots if is_lab_course else regular_time_slots

            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the appropriate time_slots array
                if time_str not in time_slots:
                    raise ValueError(f"Invalid time slot: {time_str}")

                # Validate instructor availability for the specified time
                if time_str not in instructor_availability.get(instructor, []):
                    instr_name = next((i["facuser"] for i in instructors if i["identifier"] == instructor), "Unknown")
                    print(f"Instructor {instr_name} availability: {instructor_availability.get(instructor, [])}")
                    raise ValueError(f"Instructor {instr_name} unavailable at {time_str} for {course_with_section}")

                fixed_times[course_with_section] = time_slots.index(time_str)  # Store index for CP model

            # Assign instructor and year to the course section
            instructor_assignments[course_with_section] = instructor
            course_years[course_with_section] = year

            # Group sections by base course
            if base_course not in course_sections:
                course_sections[base_course] = []
            course_sections[base_course].append(course_with_section)
            all_sections.append(course_with_section)

        # Create CP model
        model = cp_model.CpModel()
        slot_vars = {s: model.NewIntVar(0, len(regular_time_slots) - 1, f"slot_{s}") for s in all_sections}

        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)

        # Add availability constraints for each course section
        for course_with_section in all_sections:
            base_course, _ = course_with_section.rsplit("_", 1)
            is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
            time_slots = lab_time_slots if is_lab_course else regular_time_slots

            instr_id = instructor_assignments[course_with_section]
            allowed = instructor_availability.get(instr_id, [])

            # If time is fixed, only allow that slot
            if course_with_section in fixed_times:
                allowed = [fixed_times[course_with_section]]
            else:
                # Convert time slots to indexes
                allowed = [time_slots.index(ts) for ts in allowed if ts in time_slots]

            if allowed:
                model.AddAllowedAssignments([slot_vars[course_with_section]], [[slot] for slot in allowed])
            else:
                print(f"No valid time slots available for instructor {instr_id}. Skipping constraint.")

            # Initialize penalty variables
            penalty_vars = []

        # Add conflict constraints
        # Inside the loop over course pairs (i and j):
        for i in range(len(all_sections)):
            for j in range(i + 1, len(all_sections)):
                s1 = all_sections[i]
                s2 = all_sections[j]

                # Only apply same-instructor constraint if both have assigned instructors (not TBA)
                inst1 = instructor_assignments[s1]
                inst2 = instructor_assignments[s2]
                if inst1 == inst2 and inst1 != "TBA":
                    model.Add(slot_vars[s1] != slot_vars[s2])

                # Check same year and different courses
                if (course_years[s1] == course_years[s2] and
                        s1.split("_")[0] != s2.split("_")[0]):

                    # Get semesters of the two courses
                    sem1 = course_semesters[s1]
                    sem2 = course_semesters[s2]

                    if sem1 == sem2:  # Same semester → add penalty
                        same_slot = model.NewBoolVar(f'same_{s1}_{s2}')
                        model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(same_slot)
                        model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(same_slot.Not())
                        penalty_vars.append(same_slot)
                    # Else: Different semesters → no penalty (allowed to overlap)

        # Calculate total penalty for same-year conflicts
        total_penalty = model.NewIntVar(0, len(penalty_vars), 'total_penalty')
        model.Add(total_penalty == sum(penalty_vars))



        # Objective function: Minimize the maximum time slot used
        max_time = model.NewIntVar(0, len(regular_time_slots) - 1, "max_time")
        model.AddMaxEquality(max_time, [slot_vars[s] for s in all_sections])
        # Update the objective to minimize both max_time and penalties
        model.Minimize(max_time + total_penalty * 100)  # Adjust the penalty weight as needed (e.g., 100)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Log solver status and statistics
        print(f"Status: {solver.StatusName(status)}")
        print(f"Number of variables: {len(slot_vars)}")
        print(f"Number of constraints: {model.Proto().constraints.__len__()}")

        # Check if a feasible solution was found
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = {}
            for section in all_sections:
                base_course, _ = section.rsplit("_", 1)
                is_lab_course = "lab" in base_course.lower()  # Case-insensitive check
                time_slots = lab_time_slots if is_lab_course else regular_time_slots

                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(max_time)
            schedule["completion_time"] = regular_time_slots[max_slot]

            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: (lab_time_slots + regular_time_slots).index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]

            # Debugging: Log the generated schedule
            print(f"Generated Schedule: {sorted_schedule}")

            # Function to filter courses with 'TBA' instructors
            def filter_tba_courses(schedule):
                filtered_schedule = {}

                for key, value in schedule.items():
                    # Only check course entries (skip completion_time or other metadata)
                    if isinstance(value, dict) and 'instructor' in value:
                        if value['instructor'] != 'TBA':
                            filtered_schedule[key] = value
                    else:
                        # Keep non-course keys like 'completion_time'
                        filtered_schedule[key] = value

                return filtered_schedule

            # Apply filtering
            filtered_schedule = filter_tba_courses(sorted_schedule)

            # Print result
            print(f"Generated Relaxed Schedule: {filtered_schedule}")

            semester = request.form.get("semester")

            save_result = save_schedule_to_database(
                filtered_schedule,
                school_code,
                campus_code,
                academic_year,
                semester
            )

            if not save_result:
                print("Warning: Failed to save schedule to database")
            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500
