const courses = JSON.parse('{{ courses | tojson | safe }}'); // Pass courses from Flask to JavaScript
const addedCourses = new Set(); // Track added courses to prevent duplicates

document.getElementById("add-course-btn").addEventListener("click", () => {
    const dropdown = document.getElementById("course-dropdown");
    const selectedCourse = dropdown.value;

    if (!selectedCourse || addedCourses.has(selectedCourse)) {
        return; // Prevent adding empty or duplicate courses
    }

    // Add course to the set
    addedCourses.add(selectedCourse);

    // Create a new course card
    const courseCard = document.createElement("div");
    courseCard.className = "course-card";
    courseCard.innerHTML = `
        <button class="remove-course" onclick="removeCourse('${selectedCourse}')">&times;</button>
        <label style="display: flex; align-items: center;">
            <input type="checkbox" name="courses" value="${selectedCourse}" checked>
            <span style="flex: 1;">${selectedCourse}</span>
            <input type="number" id="students_${selectedCourse}" name="students_${selectedCourse}"
                   min="1" class="student-input" value="1">
        </label>
        <select name="instructor_${selectedCourse}">
            <option value="1">Instructor 1</option>
            <option value="2">Instructor 2</option>
            <option value="3">Instructor 3</option>
        </select>
    `;

    // Append the card to the container
    document.getElementById("dynamic-courses").appendChild(courseCard);
});

function removeCourse(course) {
    // Remove course from the set
    addedCourses.delete(course);

    // Remove the corresponding course card
    const courseCards = document.querySelectorAll(".course-card");
    courseCards.forEach(card => {
        const courseName = card.querySelector("input[type='checkbox']").value;
        if (courseName === course) {
            card.remove();
        }
    });
}

// Handle form submission
document.querySelector("#schedule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const response = await fetch("/schedule", { method: "POST", body: formData });
    const result = await response.json();
    const scheduleDiv = document.getElementById("schedule");
    if (result.error) {
        scheduleDiv.textContent = `Error: ${result.error}`;
    } else {
        let scheduleText = "";
        for (const section in result) {
            if (section !== "completion_time") {
                scheduleText += `Section ${section}:
                    Time: ${result[section].time},
                    Instructor: ${result[section].instructor}\n`;
            }
        }
        scheduleText += `\nSchedule completes by ${result.completion_time}.`;
        scheduleDiv.textContent = scheduleText;
    }
});