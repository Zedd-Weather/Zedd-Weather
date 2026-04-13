# Contributing to Zedd Weather

Thank you for your interest in contributing to Zedd Weather! This document provides guidelines and information to help you get started.

## Code of Conduct

By participating in this project you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## How to Contribute

### Reporting Bugs

- Search [existing issues](https://github.com/WilliamMajanja/Zedd-Weather/issues) before opening a new one.
- Use the **Bug Report** issue template.
- Include steps to reproduce, expected vs actual behaviour, and your environment (OS, Node.js version, Python version, hardware).

### Suggesting Features

- Open a **Feature Request** issue using the template.
- Describe the problem the feature solves, not just the solution.

### Submitting Pull Requests

1. **Fork** the repository and create a branch from `main`.
2. Follow the development setup below.
3. Make your changes, keeping commits focused and well-described.
4. Ensure all existing tests pass and add new tests for new functionality.
5. Open a pull request using the PR template.

## Development Setup

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker with Compose v2 (for full-stack testing)

### Frontend

```bash
npm install
npm run dev          # Vite dev server on http://localhost:5173
npm run build        # Production build
npm run lint         # TypeScript type-check (tsc --noEmit)
```

### Backend (Python)

```bash
pip install -r Zweather/requirements.txt
pytest Zweather/tests/ -v --tb=short   # Run tests
flake8 Zweather/ --select=E9,F63,F7,F82 --show-source --statistics
```

### Docker

```bash
cp .env.example .env      # Configure environment variables
docker compose up -d      # Start control plane + storage services
```

## Coding Standards

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) style.
- Use type hints where practical.
- Run `flake8` and `mypy` before submitting.

### TypeScript / React

- Use TypeScript strict mode (`tsc --noEmit` must pass).
- Place types in `src/types/`, hooks in `src/hooks/`, page components in `src/components/`.
- Use [Tailwind CSS](https://tailwindcss.com/) for styling.

### Commits

- Write clear, descriptive commit messages.
- Use present-tense imperative style (e.g. "Add alert threshold tests").

## Raspberry Pi Hardware Testing

If you have access to a Raspberry Pi 5 with a Sense HAT v2 or AI HAT+, please test hardware-specific changes on real hardware before submitting. Set sensor toggles in `.env` to match your hardware configuration.

## Security Vulnerabilities

**Do not** report security vulnerabilities through public issues. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
