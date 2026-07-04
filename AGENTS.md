# RecallOps Contributor Instructions

- Never commit secrets or credentials.
- Use Python 3.12 for backend development.
- Use Node.js 24 for frontend development and CI.
- Do not silently change runtime-version requirements.
- Do not add dependencies without explaining their purpose.
- Keep model providers behind interfaces.
- Keep memory retrieval separate from memory extraction.
- Do not use the language model to invent memory confidence or reliability scores.
- Memory ranking must remain deterministic and testable.
- Do not edit unrelated files.
- Prefer small, reviewable changes.
- Add or update tests whenever behaviour changes.
- Run relevant tests and builds before declaring a task complete.
- Do not implement features outside the current task.
- Explain changed files after every task.
