# Contributing to OpenGS Map Tool

Thank you for your interest in contributing to OpenGS Map Tool! Every contribution, big or small, helps make this project better, and we truly appreciate the time you put in.

## Getting Started

1. Fork the repository
2. Create a feature branch from `dev`
3. Make your changes
4. Open a pull request targeting the **`dev`** branch

All pull requests should be aimed at `dev` — not `main`. The `main` branch is reserved for stable releases.

## Keep It Small

Smaller, focused contributions are much easier to review, test, and merge. A PR that fixes one bug or adds one feature will almost always move faster than a large refactor or rewrite. If you have a bigger idea in mind, consider breaking it into smaller steps or opening an issue first so we can discuss the approach together.

## Testing Your Changes

There is no automated test suite, so every pull request should be manually verified before submission. At a minimum, please confirm that the application can successfully complete the full generation pipeline:

1. Import a **land image**
2. Import a **boundary image**
3. Generate **territories**
4. Generate **provinces**
5. Export **territory image**, **definitions**, and **history**
6. Export **province image**

Test with both land-only (no boundary image) and land + boundary image inputs to make sure nothing breaks.

Example images are available in the `example_input/` folder.

## Running the App

```bash
pip install -r requirements.txt
python main.py
```

## Questions or Ideas?

Feel free to open an issue if you have questions, suggestions, or want to discuss a change before starting work. We're happy to help point you in the right direction.

Thanks again for contributing!
