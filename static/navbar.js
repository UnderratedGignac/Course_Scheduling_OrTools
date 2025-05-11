// Function to add the navbar to the page
function addNavbar() {
    // Create the navbar element
    const navbar = document.createElement('div');
    navbar.className = 'navbar';
    
    // Add the buttons to the navbar
    navbar.innerHTML = `
        <button onclick="window.location.href='/index'">Home</button>
        <button onclick="window.location.href='/select-faculty'">School Selection</button>
        <button onclick="window.location.href='/previous_semester'">Previous Semester</button>
        <button onclick="window.location.href='/insert_course'">Insert Course</button>
        <button onclick="window.location.href='/edit_course'">Edit Course</button>
        <button onclick="window.location.href='/insert_instructor'">Insert Instructor</button>
        <button onclick="window.location.href='/edit_instructor'">Edit Instructor</button>
    `;
    
    // Insert the navbar at the beginning of the body
    document.body.insertBefore(navbar, document.body.firstChild);
    
    // Add padding to the body to prevent content from being hidden behind the fixed navbar
    document.body.style.paddingTop = '60px';
}

// Add the navbar when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', addNavbar);