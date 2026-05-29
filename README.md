# Skills

A repository of reusable AI agent skills.

## Available skills

### agent-first-cli

Design, implement, audit, and test command-line interfaces intended to be consumed primarily by AI agents.

## Install

This repository is published at `github.com/mustafamohsen/skills`.

List available skills:

```bash
npx skills add mustafamohsen/skills --list
```

Install the Agent-First CLI skill:

```bash
npx skills add mustafamohsen/skills --skill agent-first-cli
```

Install all skills from this repository:

```bash
npx skills add mustafamohsen/skills --skill '*'
```

Install from a local checkout:

```bash
git clone https://github.com/mustafamohsen/skills.git
cd skills
npx skills add . --skill agent-first-cli
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
