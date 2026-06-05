# Contributing to docomestria-studio

Thanks for your interest. This is a small open-source viewer on top of
[docomestria](https://github.com/MrGo2/docomestria).

## Setup

```bash
git clone https://github.com/MrGo2/docomestria-studio.git
cd docomestria-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

You'll also need a copy of `docomestria` available on your `PYTHONPATH`
(install from PyPI once published, or `pip install -e ../docomestria`).

## Run tests

```bash
pytest
ruff check .
```

## Run the dev server

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
python app.py
# open http://127.0.0.1:5050
```

## Pull requests

1. Open an issue first for non-trivial changes.
2. Keep each PR focused — one feature or fix at a time.
3. Update `CHANGELOG.md` under `## [Unreleased]` if your change is user-visible.
4. All new behavior should ship with tests.

## Code style

- Python: ruff (configured in `ruff.toml`), max line length 100.
- No emojis in source, templates, or commit messages.
- Frontend stays buildchain-free: htmx, Alpine, Tailwind, pdf.js — all via CDN.
- Each Python module aims to stay under 400 lines.

## License

By contributing you agree your work is released under the MIT License.
