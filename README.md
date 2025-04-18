# Course Scheduling with OR-Tools

## Overview

This project leverages Google's OR-Tools to solve course scheduling problems efficiently. OR-Tools is an open-source software suite for optimization, designed to tackle complex scheduling, routing, and bin packing challenges. This project focuses on automating the creation of conflict-free course schedules while optimizing resource allocation .

**Key Features:**
- Automates course scheduling using constraint programming.
- Optimizes room assignments, instructor availability, and time slots.
- Provides a flexible framework for customizing constraints and objectives.

---

## Table of Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [Project Requirements](#project-requirements)
4. [Contributing](#contributing)
5. [License](#license)
6. [Contact](#contact)

---

## Installation

To set up this project locally, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/UnderratedGignac/Course_Scheduling_OrTools.git
   ```

2. Navigate to the project directory:
   ```bash
   cd Course_Scheduling_OrTools
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

> **Note:** Ensure you have Python 3.x installed on your system. If not, download it from [python.org](https://www.python.org/downloads/).

---

## Usage

To run the course scheduling solver, execute the following command:

```bash
python main.py
```

### Customization

You can customize the scheduling constraints by modifying the configuration file (`config.json`) or directly editing the code in `main.py`. For example:
- Add new constraints (e.g., preferred time slots for instructors).
- Adjust optimization objectives (e.g., prioritize minimizing room changes).

For more details, refer to the [OR-Tools documentation](https://developers.google.com/optimization).

---

## Project Requirements

- **Python 3.x**
- **Google OR-Tools**: Installed via `pip install ortools`
- **Dependencies**: Listed in `requirements.txt`

Ensure your environment meets these requirements before running the project .

---

## Contributing

We welcome contributions to improve this project! To contribute:
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeatureName`).
3. Commit your changes (`git commit -m "Add a new feature"`).
4. Push to the branch (`git push origin feature/YourFeatureName`).
5. Open a pull request.

Please ensure your code adheres to the project's coding standards and includes appropriate tests .

---

## Contact

For questions or feedback, feel free to reach out:

- **GitHub Issues**: Open an issue in this repository.
- **Email**: eliehaddadh1@gmail.com

---
