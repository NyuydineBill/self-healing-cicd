# Documentation

Technical documentation for **Self-Healing CI/CD** and the **Nyuydine** hosted platform.

For a quick start, see the [project README](../README.md) in the repository root.

---

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture overview](architecture/overview.md) | System design, agents, data flow, defense Q&A |
| [Pipeline walkthrough](guides/pipeline-walkthrough.md) | Step-by-step five-agent repair pipeline |

## Platform (Nyuydine)

| Document | Description |
|----------|-------------|
| [Platform deployment](platform/deployment.md) | GitHub App, API, worker, Phase 1 hosted service |

## Guides

| Document | Description |
|----------|-------------|
| [Troubleshooting](guides/troubleshooting.md) | Common operational issues and fixes |

## Development

| Document | Description |
|----------|-------------|
| [Contributing](development/contributing.md) | How to contribute to the project |
| [Testing](development/testing.md) | Running and writing tests |

## Project

| Document | Description |
|----------|-------------|
| [Changelog](project/changelog.md) | Version history and upgrade notes |
| [Improvements](project/improvements.md) | Enhancement backlog |
| [Security](project/security.md) | Vulnerability reporting and security model |

## Product

| Document | Description |
|----------|-------------|
| [AI prompt library](product/prompts/README.md) | Nyuydine platform vision, MVP phasing, and GTM prompts |

## Sample projects

Demo scenarios live under [`sample_projects/`](../sample_projects/README.md) in the repository (not duplicated here).

---

## Documentation layout

```
docs/
├── README.md                 # This index
├── architecture/
│   └── overview.md
├── platform/
│   └── deployment.md
├── guides/
│   ├── pipeline-walkthrough.md
│   └── troubleshooting.md
├── development/
│   ├── contributing.md
│   └── testing.md
├── project/
│   ├── changelog.md
│   ├── improvements.md
│   └── security.md
└── product/
    └── prompts/              # AI-assisted development prompts
```
