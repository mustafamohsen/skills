# Slop to Idiomatic Skill

An explicitly invoked AI-agent skill for refactoring generated code into maintainable, ecosystem-native code without casually changing behavior.

The package uses progressive disclosure:

- `SKILL.md` contains the invocation gate, reference router, and non-negotiable rules.
- `references/refactor-workflow.md` defines the behavior-preserving workflow and verification choices.
- Only applicable language and framework references are loaded for the code in scope.
- `agents/openai.yaml` prevents implicit invocation in Codex; portable frontmatter does the same for compatible Agent Skills hosts.

## Included idiom references

- C++
- Python
- Rust
- TypeScript
- React
- TanStack Start

## Invocation

Invoke the skill directly and provide a path, diff, or precise scope:

```text
$slop-to-idiomatic src/orders
```

The skill uses red → green → refactor for bug fixes and intentional behavior changes. For pure refactors it starts from green tests, adds characterization coverage when useful, and keeps every meaningful slice green.
