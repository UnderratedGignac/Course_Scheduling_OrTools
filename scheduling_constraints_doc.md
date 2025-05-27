# Course Scheduling Constraints Documentation

## Overview

This document outlines the comprehensive set of constraints implemented in the relaxed course scheduling system. The scheduler uses Google OR-Tools' CP-SAT solver to optimize course scheduling while adhering to various academic and operational requirements.

## Core Constraint Categories

### 1. Fixed Time Constraints

**Purpose**: Accommodate user-specified time slots for specific courses.

**Implementation**:
- When a user specifies a time for a course section, the system fixes that course to the designated time slot
- Validates that the specified time exists in the global time slots array
- Ensures the assigned instructor is available at the specified time

**Code Reference**:
```python
for section, time_idx in fixed_times.items():
    model.Add(slot_vars[section] == time_idx)
```

### 2. Laboratory Course Constraints

#### 2.1 Maximum Labs Per Time Slot
**Purpose**: Prevent resource conflicts by limiting laboratory courses per time period.

**Rule**: No more than 2 laboratory courses can be scheduled in the same time slot.

**Implementation**:
- Identifies lab sections (courses ending with 'L')
- For every combination of 3 lab sections, ensures at least one pair has different time slots
- Uses boolean variables to track time slot differences

#### 2.2 Same Course Lab Grouping (Objective)
**Purpose**: Encourage lab sections of the same course to be scheduled together.

**Implementation**:
- Creates an objective function that minimizes the number of distinct time slots used by same-course labs
- Adds penalty for lab sections of the same course being in different time slots

### 3. Academic Year Constraints

#### 3.1 Same Year Course Conflicts
**Purpose**: Prevent scheduling conflicts for students in the same academic year.

**Rules**:
- Courses from the same year and semester cannot overlap unless they have a prerequisite relationship
- Different semester courses from the same year can overlap
- Prerequisite courses can overlap with their dependent courses

**Implementation**:
```python
# Allow overlap for different semesters
if semester_bc1 != semester_bc2:
    continue

# Allow overlap for prerequisite relationships
if bc2 in prereq_map.get(bc1, []) or bc1 in prereq_map.get(bc2, []):
    is_prereq = True
```

### 4. Instructor Constraints

#### 4.1 Instructor Availability
**Purpose**: Ensure instructors are only assigned to courses during their available time slots.

**Implementation**:
- Retrieves instructor availability from session data
- Creates allowed assignments constraint for each course-instructor pair
- Validates availability for user-specified fixed times

#### 4.2 Instructor Non-Overlap (Non-Lab Courses)
**Purpose**: Prevent instructors from teaching multiple non-laboratory courses simultaneously.

**Rules**:
- Non-laboratory courses assigned to the same instructor cannot overlap
- Laboratory courses can overlap with each other but not with non-laboratory courses
- TBA instructors are exempt from this constraint

**Implementation**:
```python
# Enforce no overlap for non-lab sections
for i in range(n):
    for j in range(i + 1, n):
        s1 = non_lab_sections[i]
        s2 = non_lab_sections[j]
        model.Add(slot_vars[s1] != slot_vars[s2])
```

### 5. Lecture-Laboratory Coordination

**Purpose**: Prevent conflicts between related lecture and laboratory components.

**Implementation**:
- Identifies lecture-lab pairs based on course naming conventions
- Ensures lecture and lab sections of the same course don't overlap
- Handles courses with "lab" in their name as laboratory sections

### 6. Semester-Based Scheduling

**Purpose**: Allow intelligent overlap based on academic semester requirements.

**Features**:
- Extracts semester information using the `get_semester()` function
- Permits overlap between courses offered in different semesters
- Maintains strict separation for same-semester courses (unless prerequisites)

## Constraint Hierarchy

### Hard Constraints (Must be Satisfied)
1. Fixed time assignments
2. Instructor availability
3. Maximum 2 labs per time slot
4. Instructor non-overlap for non-lab courses
5. Same-year, same-semester course separation (with prerequisite exceptions)

### Soft Constraints (Optimized)
1. Minimize time slots used by same-course labs
2. Group lab sections efficiently
3. Minimize overall schedule completion time

## Special Cases and Exceptions

### TBA Instructors
- Instructors marked as "TBA" (To Be Assigned) can teach multiple courses simultaneously
- No availability constraints applied to TBA instructors
- School-specific TBA identifiers supported (e.g., "TBA_SCHOOL_CODE")

### Laboratory Course Handling
- Laboratory courses identified by names ending with 'L'
- Special grouping logic for same-course lab sections
- Relaxed overlap rules between different lab courses with same instructor

### Prerequisite Relationships
- Fetched from database using `get_prerequisites()` function
- Allows overlap between prerequisite and dependent courses
- Reduces scheduling conflicts for sequential course requirements

## Error Handling and Fallbacks

### Validation Checks
- Validates school and campus codes
- Ensures instructor availability data exists
- Verifies time slot validity
- Confirms instructor availability for fixed times

### Constraint Relaxation
- System attempts relaxed scheduling if initial constraints cannot be satisfied
- Maintains core safety constraints while relaxing optimization preferences
- Provides detailed error messages for constraint violations

## Technical Implementation Notes

### Solver Configuration
- Uses Google OR-Tools CP-SAT solver
- Implements boolean variables for constraint tracking
- Utilizes integer variables for time slot assignments
- Applies constraint programming techniques for optimization

### Performance Considerations
- Constraint complexity scales with number of courses and instructors
- Boolean variable usage optimized for solver efficiency
- Preprocessing reduces constraint space where possible

---

**Note**: This constraint system is designed to be flexible and accommodate various academic scheduling scenarios while maintaining educational quality and resource efficiency.