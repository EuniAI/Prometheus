# 🧠 Contributing to **Prometheus**

Thank you for your interest in contributing to **Prometheus** — we’re excited to have you on board!
Your contributions help us build a stronger, smarter foundation for autonomous software reasoning. 💪

---

## 🚀 Getting Started

1. **Fork the Repository**
   Click *Fork* on GitHub and clone your fork locally:

   ```bash
   git clone https://github.com/EuniAI/Prometheus.git
   ```
2. **Set Up the Environment**
   Follow the setup instructions in [`README.md`](./README.md) to install dependencies and configure your development environment.
3. **Create a Feature Branch**
   Use a descriptive name for your branch:

   ```bash
   git checkout -b feature/short-description
   ```

---

## 🧩 Development Guidelines

### 🧱 Code Style

* We use **[ruff](https://docs.astral.sh/ruff/)** for linting and formatting.
* Before committing, run:

  ```bash
  ruff format
  ruff check --fix
  ```
* Use clear, descriptive names for variables, functions, and classes.
* Keep your code modular and well-documented.

### 🧪 Testing

* Write tests for **every new feature or bug fix**.
* Run the test suite before pushing:

  ```bash
  coverage run --source=prometheus -m pytest -v -s -m "not git"
  coverage report
  ```
* Ensure test coverage remains high and includes both **unit** and **integration** tests.

---

## 🔁 Pull Request Process

### ✅ Before You Submit

* Update relevant documentation.
* Ensure all tests and CI checks pass.
* Keep changes **focused, atomic, and well-scoped**.

### 📬 Submitting a PR

1. Open a Pull Request with a clear, descriptive title.
2. Explain *what* you changed and *why* it matters.
3. Link any related issues.
4. Provide **reproduction steps** or **test instructions**, if applicable.

### 👀 Review Process

* Maintainers will review your PR and may suggest improvements.
* Please address feedback respectfully and promptly.
* Once approved, your PR will be merged into the main branch. 🎉

---

## 🐞 Reporting Issues

If you encounter a problem:

* Open a GitHub issue with a **clear description**.
* Include steps to reproduce, logs, and screenshots if possible.
* Describe the **expected** vs **actual** behavior.

Well-documented issues are easier and faster to fix!

---

## 🤝 Code of Conduct

We expect all contributors to:

* Be respectful, inclusive, and professional.
* Welcome constructive feedback.
* Prioritize what’s best for the community.
* Show empathy and kindness to others.

We’re building a community of collaboration and innovation — let’s keep it positive and inspiring. ✨

---

## 💬 Need Help?

If you have questions or ideas:

* Start a discussion in [GitHub Discussions](../../discussions)
* Open an issue for technical topics
* Contact the maintainers directly
* Email us at 📧 **[team@euni.ai](mailto:team@euni.ai)**

---

Thank you for helping make **Prometheus** better.
Together, we’re shaping the future of autonomous code reasoning. 🚀