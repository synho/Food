# Agent Role: [Define Agent Role, egSenior Software Engineer]

## 1. Directive (The SOP)
- **Primary Goal:** [State exactly what the agent should achieve, egbuild a landing page].
- **Rules:**
  - Always use functional components with hooks.
  - Never modify production configuration files without explicit confirmation.
  - Follow the styling defined in `app/lib/theme/tokens.ts`.
- **Constraints:**
  - Do not use class-based components.
  - Use `pnpm` for all dependency management.

## 2. Orchestration (The Plan)
- Before executing any task:
  1. Toggle to **Planning Mode** in the side panel.
  2. Create an implementation plan and a detailed task list.
  3. Decompose high-level goals into logical, sequential steps.
- Revision: Revise the plan if new information arises during execution.

## 3. Execution (The Scripts)
- Use deterministic scripts to perform work and avoid hallucinations.
- **Available Commands:**
  - Install dependencies: `pnpm install`
  - Start development: `pnpm dev`
  - Run tests: `pnpm test`
- **Environment:**
  - The project root contains the `hello_world.cpp` and `package.json` files.
- **Automation:**
  - If a code error occurs, diagnose the error, update the script, and re-run automatically (Self-Annealing).
