# Copilot Instructions

## Agent Constitution

**CRITICAL RULE:** If the user corrects you on anything, you must:

1. Immediately record the correction in COPILOT.md in an appropriate section.
2. Continue with what you were doing, applying the correction.

This ensures that corrections become part of the permanent knowledge base for all future agent interactions.

**MAINTENANCE RULE:** Periodically review and organize COPILOT.md. As repeat issues emerge, progressively strengthen memory on those matters through:

- **Emphasis:** Use bold, italics, or formatting to highlight critical information.
- **Position:** Move important or frequently violated rules to more prominent locations (e.g., top of sections, Agent Constitution).
- **Repetition:** Reinforce key points by mentioning them in multiple relevant sections.
- **Alerts:** Add explicit warnings or "CRITICAL" markers for rules that are commonly missed.

This ensures that the most important and frequently needed guidance is easily accessible and hard to miss.

## Getting Started

### Quick Setup

```powershell
pixi install                      # Install dependencies and set up envs
pixi shell                        # Enter environment (optional; can use pixi run instead)
```

Create `.env` file with required credentials (see [SETUP.md](SETUP.md) for details).

### Essential Rules, Commands

Always use Pixi for commands:

```powershell
# Environment & deps
pixi install                      # Install dependencies and set up envs

# Run application
pixi run scrape                   # Run single scrape
pixi run loop                     # Run continuous loop (default interval)
pixi run loop-custom              # Run with custom interval
pixi run show-jobs                # View saved jobs

# Testing
pixi run test                     # Run the full pytest suite
pixi run test-cov                 # Tests with coverage (HTML at htmlcov/)
pixi run -e dev pytest tests/path/to/specific_test.py   # Run a single test file
pixi run -e dev pytest -k "substring_or_marker"         # Run tests matching a pattern

# Quality
pixi run format                   # Format code (ruff format)
pixi run lint                     # Lint and auto-fix (ruff check --fix)
pixi run typecheck                # Type checking (mypy src/)
pixi run check                    # Format + lint + typecheck aggregate
```

### Testing Strategy

- **Framework:** pytest with coverage reporting
- **Structure:** Tests mirror source: `src/module.py` → `tests/test_module.py`
- **Run tests:** Use `pixi run test` for suite or `pixi run test-cov` for HTML coverage
- **Coverage:** Aim for high coverage on core logic
- **Fixtures:** Use fixtures for mocking clients
- **Markers:** Custom markers (e.g., `@pytest.mark.asyncio`)
- Identify errors early with linting and type checking: `pixi run check`
- Upon running tests, if any tests fail, examine the output, explain what went wrong, and suggest fixes. Only proceed to implement the changes once you get confirmation from me.

### Docstrings

Use Google-style format. Example:

```python
def process_prompt(prompt: str) -> str:
    """Process user prompt and return formatted result.

    Args:
        prompt: Raw user input string.

    Returns:
        Formatted prompt ready for LLM.
    """
```

## Code Style

- **Max line length:** 100 characters
- **Double quotes** for strings
- **Docstrings** for public functions (Google style)

## Code Requirements

### Completeness & Style

- All code must be **complete and runnable** — no pseudocode or sketches
- Follow consistent coding style throughout the codebase
- Use descriptive variable and function names (avoid single-letter names except in loops)
- Include helpful comments for complex logic, not for obvious code
- Every function should have a docstring (Google-style)
- Follow industry standards for the specific language/framework
- Adhere to established design patterns where applicable
- Follow industry best practices for security, performance, and maintainability

### Decision Making

- **All decisions must be made by me, no assumptions**
- When fixing errors, identify root cause, explain it, and suggest fixes before implementing changes
- **Do not ask me to run any commands in the terminal** — You execute it for me after asking my permission

### Data Handling

- Use appropriate data structures (dict, list etc.)
- Implement proper validation
- Handle missing or invalid data gracefully with appropriate error responses
- Use efficient lookups and operations (avoid N² loops when O(N) is possible)

### Import Organization

- Group imports: standard library, third-party, local
- Import modules, not individual functions (e.g., `import json` not `from json import loads`)
- Place all imports at the top of the file

## Best Practices

### Testing & Changes

- Always write tests when making code changes
- Tests mirror source structure: `src/module.py` → `tests/test_module.py`

### Code Organization

- Keep functions focused on single responsibility
- Only edit files directly involved in the feature or fix

### Error Handling & Logging

- Catch and log specific exceptions, not generic `Exception`
- Use structured logging with relevant context (latency, cost, request ID)
- Return appropriate HTTP status codes (504 for timeout, 500 for errors, 400 for validation)

## Documentation Guidelines

### Content Principles

- **Single source of truth:** Update relevant files (COPILOT.md, any other .md file)
- **Avoid duplication:** Don't repeat; link instead
- **Keep it simple:** Prefer concise, focused content over comprehensive guides
- **No stale content:** Don't include version-specific information that can't be updated automatically
- **Pixi-only:** Document only Pixi for setup (pixi install, pixi shell, pixi run). Never document pip, conda, or alternatives
- **Avoid file trees:** Don't include detailed file tree structures; they become stale. Reference actual structure or provide high-level overviews instead.

### Writing Style

- **Clear and direct:** Avoid grandiose phrasing ("serves as", "plays a vital role")
- **Use simple language, describe things in a straightforward way:** Prefer "use" over "utilize", "help" over "facilitate". Assume reader has basic english proficiency.
- **When using specific technical terms** like "throttle", ensure it's necessary and adds clarity. If possible, explain the term briefly before using it.
- **Avoid formulaic scaffolding:** Skip "it's important to note", "In summary", "Overall"
- **No vague attributions:** Avoid "industry reports", "some argue" without specifics
- **No AI disclaimers:** Don't mention being an AI or apologize
- **Minimal formatting:** Use bold sparingly, avoid overuse of em dashes
- **Concrete over abstract:** Show patterns and examples
