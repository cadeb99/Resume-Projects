# Resume-Projects

Projects built over time with Python, PowerShell, macOS tooling, Claude Code, and Claude AI systems — ranging from freeCodeCamp certification exercises to production-style automation systems built for real clients.

## Contents

| Project | Description | Stack |
|---|---|---|
| [Vader-AI-Assistant](./Vader-AI-Assistant) | An always-on, voice-controlled personal AI assistant (JARVIS-style) with wake-word detection, tool-calling, a scheduled morning briefing pipeline, and a long-term SQLite memory system. In daily personal use, not a tutorial project. | Python, Claude API, ElevenLabs TTS, Google Calendar/Tasks/Gmail APIs |
| [Trashbags-SM-Automation](./Trashbags-SM-Automation) | A proof-of-concept Instagram DM automation tool that auto-replies using an AI trained on a business's product info, with human takeover detection for refunds/complaints and retry logic on sends. | Python, FastAPI, Claude API, Docker |
| [Trashbags-Ad-Analytics](./Trashbags-Ad-Analytics) | An automated weekly ad-performance reporting system for a snowpants brand. Pulls Meta ad data, competitor ads, Google Trends, and weather/ski conditions, analyzes it with Claude, and emails a formatted HTML report. Runs in a full demo mode with dummy data by default. | Python, Meta Marketing API, pytrends, Claude API, Gmail API |
| [Budget-App](./Budget-App) | A command-line budget tracker (freeCodeCamp Python Certification). Models spending categories as objects, tracks a transaction ledger, supports transfers between categories, and renders an ASCII bar chart of spending by category. | Python, OOP |
| [Polygon Area Calculator](./Polygon%20Area%20Calculator) | A `Rectangle`/`Square` OOP exercise (freeCodeCamp) covering area, perimeter, diagonal length, ASCII "picture" rendering, and inheritance via `super()`. | Python, OOP |
| [Hash Table](./Hash%20Table) | A hash table built from scratch (freeCodeCamp Data Structures track), including a simple character-sum hash function and collision handling via nested dictionaries. | Python |
| [Tower Of Hanoi](./Tower%20Of%20Hanoi) | A recursive solver for the classic Tower of Hanoi puzzle that returns every intermediate state of the three rods. | Python |
| [python-user-config-manager](./python-user-config-manager) | A CRUD system for managing user configuration settings (theme, language, notifications) via dictionaries — the first project in the freeCodeCamp Python Developer Certification. | Python |

## Project Categories

**Client / production-style automation systems** — built for actual small-business clients, designed to be deployed and run unattended:
- Vader-AI-Assistant
- Trashbags-SM-Automation
- Trashbags-Ad-Analytics

**freeCodeCamp Python Certification exercises** — foundational OOP, data structures, and CRUD projects:
- Budget-App
- Polygon Area Calculator
- Hash Table
- Tower Of Hanoi
- python-user-config-manager

## Notes

Each project has its own README with setup instructions, architecture notes, and usage examples — click into a folder above for details. The three automation systems (Vader, Trashbags-SM-Automation, Trashbags-Ad-Analytics) all include demo/simulation modes so they can be run and evaluated without live API credentials.
