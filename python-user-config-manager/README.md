# User Configuration Manager

A Python-based settings management system built as the first
certification project for the freeCodeCamp Python Developer Certification.

## Overview

This project implements a CRUD (Create, Read, Update, Delete) system
for managing user configuration settings such as theme, language,
and notifications using Python dictionaries and functions.

## Functions

- **add_setting** — Adds a new key-value setting to the configuration
- **update_setting** — Updates the value of an existing setting
- **delete_setting** — Removes a setting from the configuration
- **view_settings** — Displays all current settings in a formatted output

## Skills Demonstrated

- Python functions and parameters
- Dictionary manipulation
- String formatting and methods
- Input validation and error handling
- CRUD operations

## Certification

Built as part of the **freeCodeCamp Python Developer Certification**
All 27 automated tests passing ✅

## Usage

```python
test_settings = {'theme': 'light', 'language': 'english'}

add_setting(test_settings, ('volume', 'high'))
# Returns: "Setting 'volume' added with value 'high' successfully!"

update_setting(test_settings, ('theme', 'dark'))
# Returns: "Setting 'theme' updated to 'dark' successfully!"

delete_setting(test_settings, 'language')
# Returns: "Setting 'language' deleted successfully!"

view_settings(test_settings)
# Returns:
# Current User Settings:
# Theme: dark
# Volume: high
```
