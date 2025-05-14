from collections import defaultdict

from flask import request, jsonify, session
from ortools.sat.python import cp_model

from Get_Data_From_Database.Get_Instructor_From_database import get_instructors_by_school
from Get_Data_From_Database.Get_Prerequisites_From_Database import get_prerequisites
from Mapping.Semester_Mapping import get_semester
from time_slots import time_slots


def generate_relaxed_schedule():
    try:
        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))
        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")
        academic_year = request.form.get("academic_year")
        semester = request.form.get("semester")
        TBA_isntructor = "TBA_" + school_code
        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400
        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400
        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        print(f"[DEBUG] Session instructor_availability retrieved: {instructor_availability}")
        if not instructor_availability:
            return jsonify({"error": "Instructor availability data is missing."}), 400
        # Debugging: Log the instructor availability data
        print(f"Instructor Availability Data: {instructor_availability}")
        # Process selected courses
        all_sections = []
        selected_courses = request.form.getlist("courses")
        selected_base_courses = [course.rsplit("_", 1)[0] for course in selected_courses]

        # Fetch only relevant prerequisites
        prereq_map = get_prerequisites(selected_base_courses)
        if not prereq_map:
            print("No prerequisites found for the selected courses.")
        for course_with_section in selected_courses:
            base_course, section_letter = course_with_section.rsplit("_", 1)
            instructor_key = f"instructor_{course_with_section}"
            instructor = request.form.get(instructor_key, "TBA")  # Default to TBA
            instructor_assignments[course_with_section] = instructor
            year = int(request.form[f"year_{course_with_section}"])
            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the global time_slots array
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
        slot_vars = {s: model.NewIntVar(0, len(time_slots) - 1, f"slot_{s}") for s in all_sections}
        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)
        # Handle lab constraints
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)
        same_course_groups = defaultdict(list)
        # Add an objective to minimize the number of distinct time slots for same-course labs
        objective = model.NewIntVar(0, len(all_sections), "objective")
        for base in same_course_groups:
            group = same_course_groups[base]
            if len(group) < 2:
                continue
            # Create a variable for each pair of sections in the group
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    s1 = group[i]
                    s2 = group[j]
                    # If s1 and s2 are in different slots, add 1 to the objective
                    diff = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff.Not())
                    model.Add(objective + diff <= objective + 1)
        # Minimize the objective (prioritize same slots)
        model.Minimize(objective)
        # --- NEW CONSTRAINT: MAX 2 LABS PER TIME SLOT ---
        # Collect all lab sections
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)
        # Ensure no time slot has more than 2 lab courses
        for i in range(len(lab_sections)):
            for j in range(i + 1, len(lab_sections)):
                for k in range(j + 1, len(lab_sections)):
                    s1 = lab_sections[i]
                    s2 = lab_sections[j]
                    s3 = lab_sections[k]
                    # Create boolean variables to track differences
                    diff1 = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff1)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff1.Not())
                    diff2 = model.NewBoolVar(f"{s1}_{s3}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s3]).OnlyEnforceIf(diff2)
                    model.Add(slot_vars[s1] == slot_vars[s3]).OnlyEnforceIf(diff2.Not())
                    diff3 = model.NewBoolVar(f"{s2}_{s3}_diff")
                    model.Add(slot_vars[s2] != slot_vars[s3]).OnlyEnforceIf(diff3)
                    model.Add(slot_vars[s2] == slot_vars[s3]).OnlyEnforceIf(diff3.Not())
                    # At least one difference must be true
                    model.AddBoolOr([diff1, diff2, diff3])
        # --- RELAXED CONSTRAINT: SAME YEAR COURSES CAN OVERLAP BASED ON SEMESTER ---
        # Group courses by year and base course
        courses_by_year = defaultdict(dict)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            year = course_years[section]
            if year not in courses_by_year:
                courses_by_year[year] = defaultdict(list)
            courses_by_year[year][base_course].append(section)

        # Allow overlapping for courses from the same year if they are prerequisites or different semesters
        for year, base_courses in courses_by_year.items():
            base_list = list(base_courses.keys())
            for i in range(len(base_list)):
                for j in range(i + 1, len(base_list)):
                    bc1 = base_list[i]
                    bc1_sections = base_courses[bc1]
                    bc2 = base_list[j]
                    bc2_sections = base_courses[bc2]

                    # Extract semester information
                    semester_bc1 = get_semester(bc1)
                    semester_bc2 = get_semester(bc2)

                    # Allow overlap for different semesters
                    if semester_bc1 != semester_bc2:
                        print(f"Allowing overlap between {bc1} and {bc2} due to different semesters.")
                        continue

                    # Check for prerequisite relationship
                    is_prereq = False
                    if bc2 in prereq_map.get(bc1, []) or bc1 in prereq_map.get(bc2, []):
                        is_prereq = True

                    if is_prereq:
                        print(f"Allowing overlap between {bc1} and {bc2} due to prerequisite relationship.")
                    else:
                        print(f"Preventing overlap between {bc1} and {bc2}.")
                        # Prevent overlap for same semester and non-prerequisite courses
                        for s1 in bc1_sections:
                            for s2 in bc2_sections:
                                model.Add(slot_vars[s1] != slot_vars[s2])
        # Ensure no instructor is assigned to more than one course at the same time
        instructor_sections = defaultdict(list)
        for section in all_sections:
            instr_id = instructor_assignments[section]# Skip TBA instructors (they can teach multiple courses at the same time)
            if instr_id == "TBA" or instr_id == TBA_isntructor :
                continue
            instructor_sections[instr_id].append(section)

        for instr_id, sections in instructor_sections.items():
            # Separate lab sections and non-lab sections
            lab_sections = []
            non_lab_sections = []
            for s in sections:
                base_course = s.rsplit('_', 1)[0]
                if base_course.endswith('L'):
                    lab_sections.append(s)
                else:
                    non_lab_sections.append(s)

            # Enforce no overlap for non-lab sections
            n = len(non_lab_sections)
            if n > 1:
                for i in range(n):
                    for j in range(i + 1, n):
                        s1 = non_lab_sections[i]
                        s2 = non_lab_sections[j]
                        model.Add(slot_vars[s1] != slot_vars[s2])

            # Prevent lab sections from overlapping with non-lab courses
            for lab_section in lab_sections:
                for other_section in sections:
                    if lab_section == other_section:
                        continue
                    # Check if the other section is a lab
                    other_base = other_section.rsplit('_', 1)[0]
                    is_other_lab = other_base.endswith('L')
                    if not is_other_lab:
                        model.Add(slot_vars[lab_section] != slot_vars[other_section])
        # --- NEW CONSTRAINT: PREVENT LECTURE AND LAB OVERLAP ---
        # Identify lecture-lab pairs
        # Prevent lecture and lab overlaps (similar to regular scheduler):
        lecture_lab_pairs = defaultdict(list)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            if 'lab' in base_course.lower():  # Assuming lab courses have "lab" in their name
                lecture_base = base_course.replace('Lab', '')  # Adjust based on naming
                lecture_lab_pairs[lecture_base].append(section)
            else:
                lecture_lab_pairs[base_course].append(section)

        for base, sections in lecture_lab_pairs.items():
            lectures = [s for s in sections if 'lab' not in s.lower()]
            labs = [s for s in sections if 'lab' in s.lower()]
            for lecture in lectures:
                for lab in labs:
                    model.Add(slot_vars[lecture] != slot_vars[lab])

        # Add availability constraints for each course section
        for course_with_section in all_sections:
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
        # Solve the model without an objective function
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
                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(slot_vars[max(slot_vars, key=lambda s: solver.Value(slot_vars[s]))])
            schedule["completion_time"] = time_slots[max_slot]
            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: time_slots.index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]
            # Debugging: Log the generated schedule

            print(f"Generated Relaxed Schedule: {sorted_schedule}")

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

            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")
    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


'''def generate_schedule():
    try:
        # Log received form data for debugging
        print("Received Form Data:", dict(request.form))

        # Initialize variables
        course_sections = {}
        instructor_assignments = {}
        course_years = {}
        fixed_times = {}

        # Retrieve school_code and campus_code from hidden fields
        school_code = request.form.get("school_code")
        campus_code = request.form.get("campus_code")

        # Validate school_code and campus_code
        if not school_code or not campus_code:
            return jsonify({"error": "School code and campus code are required."}), 400

        # Fetch instructors for the selected school
        instructors = get_instructors_by_school(school_code)
        if not instructors:
            return jsonify({"error": "No instructors available for the selected school."}), 400

        # Process instructor availability from session
        instructor_availability = session.get("instructor_availability", {})
        print(f"[DEBUG] Session instructor_availability retrieved: {instructor_availability}")
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
            instructor = request.form[f"instructor_{course_with_section}"]
            year = int(request.form[f"year_{course_with_section}"])

            # Process user-specified time (optional field)
            time_str = request.form.get(f"time_{course_with_section}", "").strip()
            if time_str:
                # Validate time slot exists in the global time_slots array
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
        slot_vars = {s: model.NewIntVar(0, len(time_slots) - 1, f"slot_{s}") for s in all_sections}

        # Add fixed time constraints (if user specified a time)
        for section, time_idx in fixed_times.items():
            model.Add(slot_vars[section] == time_idx)

        # Handle lab constraints
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)

        # Enforce same course lab sections to have the same slot
        same_course_groups = defaultdict(list)
        for s in lab_sections:
            base = s.rsplit('_', 1)[0]
            same_course_groups[base].append(s)
        for group in same_course_groups.values():
            if len(group) < 2:
                continue
            first = group[0]
            for s in group[1:]:
                model.Add(slot_vars[s] == slot_vars[first])


        # Handle same instructor labs (different courses) with penalties
        penalties = []
        instructor_lab_sections = defaultdict(list)
        for s in lab_sections:
            instr = instructor_assignments[s]
            instructor_lab_sections[instr].append(s)
        for instr, labs in instructor_lab_sections.items():
            for i in range(len(labs)):
                for j in range(i + 1, len(labs)):
                    s1 = labs[i]
                    s2 = labs[j]
                    base1 = s1.rsplit('_', 1)[0]
                    base2 = s2.rsplit('_', 1)[0]
                    if base1 == base2:
                        continue  # already grouped by same course
                    diff_var = model.NewBoolVar(f'diff_{s1}_{s2}')
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff_var)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff_var.Not())
                    penalties.append(diff_var)

        # --- NEW CONSTRAINT: MAX 2 LABS PER TIME SLOT ---
        # Collect all lab sections
        lab_sections = []
        for s in all_sections:
            base_course = s.rsplit('_', 1)[0]
            if base_course.endswith('L'):
                lab_sections.append(s)

        # Ensure no time slot has more than 2 lab courses
        for i in range(len(lab_sections)):
            for j in range(i + 1, len(lab_sections)):
                for k in range(j + 1, len(lab_sections)):
                    s1 = lab_sections[i]
                    s2 = lab_sections[j]
                    s3 = lab_sections[k]

                    # Create boolean variables to track differences
                    diff1 = model.NewBoolVar(f"{s1}_{s2}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(diff1)
                    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(diff1.Not())

                    diff2 = model.NewBoolVar(f"{s1}_{s3}_diff")
                    model.Add(slot_vars[s1] != slot_vars[s3]).OnlyEnforceIf(diff2)
                    model.Add(slot_vars[s1] == slot_vars[s3]).OnlyEnforceIf(diff2.Not())

                    diff3 = model.NewBoolVar(f"{s2}_{s3}_diff")
                    model.Add(slot_vars[s2] != slot_vars[s3]).OnlyEnforceIf(diff3)
                    model.Add(slot_vars[s2] == slot_vars[s3]).OnlyEnforceIf(diff3.Not())

                    # At least one difference must be true
                    model.AddBoolOr([diff1, diff2, diff3])

        # --- NEW CONSTRAINT: SAME YEAR COURSES CANNOT CONFLICT ---
        # Group courses by year and base course
        courses_by_year = defaultdict(dict)
        for section in all_sections:
            base_course = section.rsplit('_', 1)[0]
            year = course_years[section]
            if year not in courses_by_year:
                courses_by_year[year] = {}
            if base_course not in courses_by_year[year]:
                courses_by_year[year][base_course] = []
            courses_by_year[year][base_course].append(section)

        # Ensure no overlapping slots for different base courses in the same year
        for year, base_courses in courses_by_year.items():
            # For all pairs of different base courses in the same year
            base_list = list(base_courses.keys())
            for i in range(len(base_list)):
                for j in range(i + 1, len(base_list)):
                    bc1 = base_list[i]
                    bc1_sections = base_courses[bc1]
                    bc2 = base_list[j]
                    bc2_sections = base_courses[bc2]
                    # Ensure no section from bc1 and bc2 share the same slot
                    for s1 in bc1_sections:
                        for s2 in bc2_sections:
                            model.Add(slot_vars[s1] != slot_vars[s2])

        # Add availability constraints for each course section
        for course_with_section in all_sections:
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

                # Add constraints between course sections
        for i in range(len(all_sections)):
            for j in range(i + 1, len(all_sections)):
                s1 = all_sections[i]
                s2 = all_sections[j]
                # Same instructor constraint with exception for labs
                if instructor_assignments[s1] == instructor_assignments[s2]:
                    # Check if both are lab courses
                    base1 = s1.rsplit("_", 1)[0]
                    base2 = s2.rsplit("_", 1)[0]
                    if base1.endswith('L') and base2.endswith('L'):
                        # Allow same instructor for labs to share a slot
                        continue
                    else:
                        model.Add(slot_vars[s1] != slot_vars[s2])
                    # Same year but different course constraint
                    if course_years[s1] == course_years[s2] and s1.rsplit("_", 1)[0] != s2.rsplit("_", 1)[0]:
                        model.Add(slot_vars[s1] != slot_vars[s2])

                # Group sections by instructor
            instructor_sections = defaultdict(list)
            for section in all_sections:
                    instr_id = instructor_assignments[section]
                    instructor_sections[instr_id].append(section)

            for instr_id, sections in instructor_sections.items():
                # Filter out lab sections (base course ends with 'L')
                non_lab_sections = []
                for s in sections:
                    base_course = s.rsplit('_', 1)[0]
                    if not base_course.endswith('L'):
                        non_lab_sections.append(s)

                # Only apply the constraint if there are 3+ non-lab courses
                n = len(non_lab_sections)
                if n < 3:
                    continue

                times = [slot_vars[section] for section in non_lab_sections]
                for i in range(n):
                    for j in range(i + 1, n):
                        for k in range(j + 1, n):
                            a, b, c = times[i], times[j], times[k]
                            max_var = model.NewIntVar(0, len(time_slots) - 1, f'max_{instr_id}_{i}_{j}_{k}')
                            model.AddMaxEquality(max_var, [a, b, c])
                            min_var = model.NewIntVar(0, len(time_slots) - 1, f'min_{instr_id}_{i}_{j}_{k}')
                            model.AddMinEquality(min_var, [a, b, c])
                            diff = model.NewIntVar(-len(time_slots), len(time_slots), f'diff_{instr_id}_{i}_{j}_{k}')
                            model.Add(diff == max_var - min_var)
                            model.Add(diff > 2)  # Ensure non-lab courses aren't too close

                    # Set the objective function
        max_time = model.NewIntVar(0, len(time_slots) - 1, "max_time")
        model.AddMaxEquality(max_time, [slot_vars[s] for s in all_sections])
        if penalties:
                sum_penalty = model.NewIntVar(0, len(penalties), "sum_penalty")
                model.Add(sum_penalty == sum(penalties))
                model.Minimize(max_time + sum_penalty)
        else:
                model.Minimize(max_time)

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
                slot_index = solver.Value(slot_vars[section])
                schedule[section] = {
                    "time": time_slots[slot_index],
                    "instructor": instructor_assignments[section],
                }
            max_slot = solver.Value(max_time)
            schedule["completion_time"] = time_slots[max_slot]

            # Sort the schedule strictly by the order of time_slots
            sorted_sections = sorted(
                ((section, details) for section, details in schedule.items() if section != "completion_time"),
                key=lambda item: time_slots.index(item[1]["time"])
            )
            sorted_schedule = {section: details for section, details in sorted_sections}
            sorted_schedule["completion_time"] = schedule["completion_time"]

            # Debugging: Log the generated schedule
            print(f"Generated Schedule: {sorted_schedule}")

            # Return the sorted schedule as JSON
            return jsonify(sorted_schedule)
        else:
            raise Exception("No feasible schedule found. Please adjust constraints.")

    except Exception as e:
        # Log and return any errors
        print(f"Error: {e}")
        # Attempt to generate a relaxed schedule as a fallback
        print("Attempting to generate a relaxed schedule...")
        relaxed_schedule_response = generate_relaxed_schedule()

        # Check if the response is a tuple (common in Flask when returning JSON + status code)
        if isinstance(relaxed_schedule_response, tuple):
            relaxed_schedule, status_code = relaxed_schedule_response  # Unpack the tuple
        else:
            relaxed_schedule, status_code = relaxed_schedule_response, 200  # Assume success if not a tuple

        # If the relaxed schedule was successfully generated, return it
        if status_code == 200:
            print("Relaxed schedule generated successfully.")
            return relaxed_schedule  # Return the relaxed schedule
        else:
            # If both methods fail, return the original error and the relaxed schedule error
            relaxed_error = relaxed_schedule.json.get("error", "Unknown error in relaxed schedule.") if hasattr(
                relaxed_schedule, "json") else "Unknown error"
            return jsonify({"error": str(e), "relaxed_error": relaxed_error}), 500
'''
