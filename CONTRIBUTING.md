# Contributing to TokStat

Thank you for your interest in contributing to **TokStat**! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

---

## 🛠️ Development Setup

TokStat requires **Python 3.9+**. We recommend using [`uv`](https://github.com/astral-sh/uv) for fast and reliable dependency management, but standard `pip` and `venv` work as well.

### 1. Fork & Clone

Fork the repository on GitHub, then clone your fork locally:

```bash
git clone https://github.com/<your-username>/tokstat.git
cd tokstat
```

### 2. Create a Virtual Environment

Using `uv`:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Using standard `venv`:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies in Editable Mode

Install TokStat along with development dependencies:

Using `uv`:
```bash
uv pip install -e ".[dev]"
```

Using `pip`:
```bash
pip install -e ".[dev]"
```

---

## 🧪 Testing & Code Quality

Before opening a Pull Request, please ensure all lints and tests pass locally.

### Linting & Formatting

We use [Ruff](https://github.com/astral-sh/ruff) for linting and code style checks:

```bash
# Run linter checks
ruff check .

# Fix auto-fixable lint errors
ruff check --fix .
```

### Running Unit Tests

We use [pytest](https://docs.pytest.org/) for running our test suite:

```bash
pytest
```

Ensure all tests pass before submitting your PR.

---

## 🔀 Pull Request Guidelines

1. **Create a Topic Branch**: Work on a descriptive branch (e.g., `git checkout -b feat/add-telemetry-source` or `fix/db-connection-leak`).
2. **Write Clean Commit Messages**: Use standard, descriptive commit messages.
3. **Add & Update Tests**: Include test cases covering any new functionality or bug fixes.
4. **Keep PRs Focused**: Try to address one specific issue or feature per PR to streamline code reviews.
5. **Verify CI**: Ensure all GitHub Actions checks (linting with Ruff, tests across Python 3.9-3.12) pass on your Pull Request.

---

## 🐛 Reporting Issues & Feature Requests

- **Bug Reports**: Search existing issues first. If not found, open a new issue with a clear title, reproduction steps, expected vs. actual behavior, and relevant logs or environment details.
- **Feature Requests**: Open an issue detailing the use case, proposed feature design, and how it benefits TokStat users.

---

## 📄 License

By contributing to TokStat, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
