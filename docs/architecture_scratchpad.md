# Technical Architecture Scratchpad

*(Saved for the upcoming Architecture Document)*

## Required Tools for the Agent
1. **Web Search Tool**: For discovering current dates of festivals, seasonal weather, and general travel logistics.
2. **Reddit Search Tool**: A specialized tool/parameter to query Reddit discussions for authentic user tips and safety advice for solo travelers.
3. **Media Search Tool**: To fetch relevant images and videos of suggested locations/events to generate visually rich responses.
4. **Multi-turn Chat Interface**: To support the agent's ability to ask clarifying questions (e.g., about budget constraints or climate preferences) and refine the itinerary.

## Evaluation & Compliance
The core intelligence of the planner will be driven by a highly structured System Prompt. This prompt is designed to comply with the 9-point evaluation criteria for step-by-step reasoning, strict tool usage separation, error handling, mandatory safety assessments, and structured outputs.
