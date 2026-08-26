# Testing with pytest — deck list

Approved course structure (23 decks, fundamentals → advanced).
See `.internal/testing-with-pytest/progress.md` for per-deck build status.

## Foundations
1. What pytest Is and Why It Replaced unittest
2. Installing pytest and Running Your First Test
3. Test Discovery Conventions
4. Writing Assertions with Plain assert

## Fixtures
5. Assertion Rewriting and Failure Messages
6. Fixtures Fundamentals
7. Fixture Scopes
8. conftest.py and Fixture Sharing
9. Built-in Fixtures: tmp_path, capsys, monkeypatch
10. Yield Fixtures and Teardown

## Parametrize & Markers
11. Parametrizing Tests
12. Parametrizing Fixtures
13. Marking Tests: skip, skipif, xfail
14. Custom Markers and Registration
15. Testing Exceptions with pytest.raises
16. Testing Warnings with pytest.warns

## Plugins & Tooling
17. Mocking with pytest-mock
18. Measuring Coverage with pytest-cov
19. Running Tests in Parallel with pytest-xdist
20. Configuring pytest: pyproject.toml and ini Options
21. Organizing a Test Suite: src Layout
22. Debugging Failing Tests: -v, -x, -k, --pdb
23. Common pytest Anti-Patterns and Best Practices

## Prerequisites this course points to instead of re-teaching
- `python-basics` — Python fundamentals (this course assumes you already know Python)
- `testing-in-software-engineering` — general testing vocabulary (unit test, integration test, flaky test, test doubles) this course specializes for pytest specifically
