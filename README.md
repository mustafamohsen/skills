# Skills

A repository of reusable AI agent skills installable with Vercel's [`skills`](https://github.com/vercel-labs/skills) CLI.

## Available skills

### agent-first-cli

Design, implement, audit, and test command-line interfaces intended to be consumed primarily by AI agents.

## Install

List available skills:

```bash
npx skills add <owner>/<repo> --list
```

Install the Agent-First CLI skill:

```bash
npx skills add <owner>/<repo> --skill agent-first-cli
```

Install from a local checkout:

```bash
npx skills add . --skill agent-first-cli
```

Install all skills from this repository:

```bash
npx skills add <owner>/<repo> --skill '*'
```

## Repository layout

Each skill lives under `skills/<skill-name>/` and includes a `SKILL.md` file with YAML frontmatter.

```text
skills/
  agent-first-cli/
    SKILL.md
    README.md
    docs/
    examples/
    scripts/
    tasks/
    templates/
```
