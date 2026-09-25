# Contributing

Create a virtual environment and install `requirements-dev.txt`.

Before opening a pull request:

```bash
ruff check .
pytest
```

Changes to workflow behavior should include tests. Do not commit databases, secrets, generated runtime data, or editor metadata.
