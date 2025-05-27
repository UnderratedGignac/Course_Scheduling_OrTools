# Summer Course Scheduling Constraints Documentation

## Overview

This document outlines the specialized constraint system implemented for summer course scheduling. The summer scheduler is designed for intensive, condensed academic sessions with unique time slot configurations and specific academic requirements different from regular semester scheduling.

## Summer-Specific Features

### Time Slot Configuration

**Regular Courses**:
- `MWTTH 8:00-9:50`
- `MWTTH 10:00-11:50` 
- `MWTTH 12:00-1:50`

**Laboratory Courses**:
- `MWTH 8:00-9:50`
- `MWTH 10:00-11:50`
- `MWTH 12:00-1:50`

**Key Differences**:
- Regular courses meet Monday through Thursday (MWTTH)
- Lab courses meet Monday, Wednesday, Thursday (MWTH) - excluding Tuesday
- Condensed schedule with only 3 time slots per day type
- Extended session durations (1 hour 50 minutes) for intensive learning

## Core Constraint Categories

### 1. Course Type Differentiation

**Purpose**: Handle different scheduling requirements for regular vs. laboratory courses.

**Implementation**:
- Automatic detection of lab courses using case-insensitive keyword matching
- Separate time slot arrays for regular and lab courses
- Dynamic assignment based on course type

**Code Reference**:
```python
is_lab_course = "lab" in base_course.lower()
time_slots = lab_time_slots if is_lab_course else regular_time_slots
```

### 2. Theory-Lab Course Separation

**Purpose**: Prevent overlap between related theory and laboratory components of the same course.

**Rule**: Lab courses (ending with 'L') cannot be scheduled at the same time as their corresponding theory courses.

**Implementation**:
- Identifies lab courses by 'L' suffix (e.g., 'CSCI250L')
- Maps to corresponding theory course (e.g., 'CSCI250')
- Enforces different time slot assignment

**Code Reference**:
```python
if base_s.endswith("L"):
    theory_course_base = base_s[:-1]  # Remove 'L'
    for t in all_sections:
        base_t = t.rsplit("_", 1)[0]
        if base_t == theory_course_base:
            model.Add(slot_vars[s] != slot_vars[t])
```

### 3. Fixed Time Constraints

**Purpose**: Accommodate user-specified scheduling preferences.

**Implementation**:
- Validates fixed times against appropriate time slot array (regular vs. lab)
- Ensures instructor availability for fixed time assignments
- Locks course sections to specified time slots

### 4. Instructor Availability Constraints

**Purpose**: Ensure instructors are only assigned during their available periods.

**Features**:
- Course-type aware availability checking
- Separate validation for regular and lab time slots
- Integration with instructor availability database

**Implementation**:
```python
allowed = [time_slots.index(ts) for ts in allowed if ts in time_slots]
if allowed:
    model.AddAllowedAssignments([slot_vars[course_with_section]], [[slot] for slot in allowed])
```

### 5. Instructor Conflict Prevention

**Purpose**: Prevent instructors from teaching multiple courses simultaneously.

**Rules**:
- Same instructor cannot teach different courses at the same time
- TBA (To Be Assigned) instructors are exempt
- School-specific TBA handling supported

**Implementation**:
```python
if inst1 == inst2 and inst1 != "TBA" and inst1 != TBA_isntructor:
    model.Add(slot_vars[s1] != slot_vars[s2])
```

### 6. Academic Year and Semester Conflicts

#### 6.1 Same Year Course Management
**Purpose**: Handle scheduling conflicts for students in the same academic year.

**Rules**:
- Courses from the same year and same semester receive penalty for overlapping
- Different semester courses from the same year can overlap without penalty
- Uses soft constraint approach with penalty variables

#### 6.2 Semester-Based Conflict Resolution
**Purpose**: Allow intelligent scheduling based on semester offerings.

**Implementation**:
```python
if sem1 == sem2:  # Same semester → add penalty
    same_slot = model.NewBoolVar(f'same_{s1}_{s2}')
    model.Add(slot_vars[s1] == slot_vars[s2]).OnlyEnforceIf(same_slot)
    model.Add(slot_vars[s1] != slot_vars[s2]).OnlyEnforceIf(same_slot.Not())
    penalty_vars.append(same_slot)
```

## Constraint Hierarchy

### Hard Constraints (Must be Satisfied)
1. **Theory-Lab Separation**: Related theory and lab courses cannot overlap
2. **Fixed Time Assignments**: User-specified times must be honored
3. **Instructor Availability**: Courses only scheduled during instructor available times
4. **Instructor Non-Overlap**: Same instructor cannot teach multiple courses simultaneously

### Soft Constraints (Penalized but Flexible)
1. **Same-Year Same-Semester Conflicts**: Penalty applied but not prohibited
2. **Schedule Completion Time**: Minimize latest scheduled course

## Optimization Objectives

### Primary Objective
Minimize the maximum time slot used across all courses to create compact schedules.

### Secondary Objective  
Minimize same-year same-semester course conflicts through penalty system.

**Objective Function**:
```python
model.Minimize(max_time + total_penalty * 100)
```

**Weight Configuration**:
- Penalty weight: 100 (adjustable)
- Balances schedule compactness with conflict avoidance

## Summer-Specific Considerations

### Compressed Schedule Benefits
- **Intensive Learning**: Extended daily sessions support focused study
- **Reduced Conflicts**: Fewer time slots reduce scheduling complexity  
- **Flexible Lab Scheduling**: Separate lab slots accommodate equipment constraints

### Course Type Handling
- **Automatic Detection**: Smart identification of lab vs. regular courses
- **Appropriate Time Slots**: Ensures courses use correct scheduling framework
- **Validation**: Prevents mismatched time slot assignments

### Academic Calendar Integration
- **Semester Awareness**: Uses semester mapping for conflict resolution
- **Year-Based Grouping**: Manages student cohort scheduling needs
- **Prerequisite Consideration**: Integrates with semester-based course sequences

## Error Handling and Validation

### Input Validation
- School and campus code verification
- Instructor availability data presence
- Time slot format validation
- Course type identification accuracy

### Constraint Feasibility
- Graceful handling of over-constrained problems
- Detailed error reporting for constraint violations
- Fallback mechanisms for scheduling conflicts

### Debugging Support
- Comprehensive logging of constraint additions
- Solver statistics reporting
- Schedule generation tracking

## Technical Implementation

### Solver Configuration
- **Engine**: Google OR-Tools CP-SAT solver
- **Variable Types**: Integer variables for time slots, Boolean for penalties
- **Constraint Types**: Linear constraints, logical implications
- **Optimization**: Multi-objective with weighted penalties

### Performance Characteristics
- **Scalability**: Efficient for typical summer course loads
- **Memory Usage**: Optimized variable creation
- **Solve Time**: Fast convergence for summer-sized problems

### Data Structures
- **Time Slot Arrays**: Separate regular and lab configurations
- **Course Mapping**: Base course to section relationships
- **Instructor Tracking**: Availability and assignment management
- **Penalty System**: Boolean variable penalty accumulation

---

**Note**: The summer scheduling system prioritizes schedule compactness and intensive learning formats while maintaining academic integrity and resource availability constraints. The penalty-based approach for same-semester conflicts provides flexibility needed for summer session complexity.