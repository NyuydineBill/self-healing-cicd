# AI prompt library

These files guide AI-assisted development of Nyuydine from thesis prototype to commercial platform.

They are **not** a single-day build list. They are layered instructions: vision, phasing, and decision rules.

---

## Assembly order

Always use prompts in this order:

1. [`mvp.txt`](mvp.txt) — What to build now and what to defer (**read first**)
2. [`final_decision_rule.txt`](final_decision_rule.txt) — How to choose between approaches
3. [`master2.txt`](master2.txt) — Long-term platform vision and architecture
4. [`company_identity.txt`](company_identity.txt) — Brand, mission, positioning

Then add context-specific files only when relevant:

| File | Use when |
|------|----------|
| [`plugin_system.txt`](plugin_system.txt) | Designing adapters or provider interfaces |
| [`backend.txt`](backend.txt) | Building or extending the API / worker layer |
| [`frontend.txt`](frontend.txt) | Phase 2+ dashboard work only |
| [`dashboard.txt`](dashboard.txt) | Phase 2+ dashboard UX spec |
| [`engineering_command_center.txt`](engineering_command_center.txt) | Phase 4 positioning / full product UX |
| [`product_ecosystem.txt`](product_ecosystem.txt) | Naming and modular product boundaries (future) |
| [`website_architecture.txt`](website_architecture.txt) | Marketing site and public domains (later) |
| [`gtm.txt`](gtm.txt) | Go-to-market, ICP, pricing hypothesis |

---

## Deprecated

[`master1.txt`](master1.txt) — Superseded by `master2.txt` + `mvp.txt`. Keep for reference only.

---

## Key principle

| Document | Answers |
|----------|---------|
| `mvp.txt` | "What do we build this sprint?" |
| `final_decision_rule.txt` | "Which design option do we pick?" |
| `master2.txt` | "Where is the platform going in 2–3 years?" |
| `company_identity.txt` | "Who are we and what do we promise?" |

Vision without phasing causes over-engineering. Phasing without vision causes rework. Use both.

---

## Current focus

**Phase 1 — GitHub Reliability Engine**

GitHub App + hosted worker + repair API + org-scoped memory. No dashboard. No Jenkins. No knowledge graph yet.

See also [`docs/platform/deployment.md`](../../platform/deployment.md) for the running service.
