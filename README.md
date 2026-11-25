# NPI Agent Toolkit

An agent-based assistant for **New Product Introduction (NPI)** of fibre-optic components (fibre array units and fan-out cables) at a contract manufacturer. An engineer hands a customer document to a manager agent; station agents draft the engineering documents one station at a time, and every station stops for the engineer's review.

The factory, customers and cases in `input/` are sample data built for developing and testing this tool.

## What it does

| Station | Runs when | Draft output |
| --- | --- | --- |
| DFM / change impact | A draft spec (A0) or an ECR (B0 onwards) arrives | DFM reply or change-impact email (`.eml`) |
| Engineering release | DFM reviewed and the customer's decision recorded | Product specification (`.docx`), BOM (`.xlsx`), drawing (`.pdf`), 3D model (`.step`) |
| Costing | Engineering release reviewed | Unit cost sheet with live formulas (`.xlsx`) |
| PO check | A customer PO arrives | PO check result (`.md`) |
| Supply chain | PO check reviewed | Material preparation / change notice (`.eml`) |

Principles:
- **No invented numbers.** Every number in an output must appear in a cited source (customer document, factory master data, operating rules, or a value the engineer gave). Anything without a source is written as `待工程師填寫` ("to be filled in by the engineer") and listed when the station stops.
- **The engineer decides.** Each station stops at "awaiting review"; nothing moves on until the engineer approves.
- **Code computes, agents judge.** Reading files, quantities, prices and formulas are done by Python; the agents only write the judgement (risks, proposals, design choices) into `judgement.json`, which is checked before anything is rendered.
- **Drafts only.** The tool sends no email and writes to no external system.

## Requirements

- Python 3.11
- [Claude Code](https://claude.com/claude-code) (the manager is a slash command; the stations are Claude Code subagents)

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Usage

In Claude Code, from the project root:

```
/npi input/<case>/<revision>/01_Customer_Draft_Spec/<draft spec>.docx
/npi status <NPI number>
```

The manager runs `intake`, shows the timeline, dispatches the next station and stops for review. Reply `可以` to approve, or give a value in the conversation to change one cell. Outputs go to `output/<NPI number>/<revision>/<station>/`.

The underlying CLI can also be used directly:

```bash
.venv/bin/python -m npi intake <file>
.venv/bin/python -m npi status <NPI>
.venv/bin/python -m npi prepare|render|approve|reopen <NPI> <rev> <station>
.venv/bin/python -m npi compare <NPI> <rev>    # list differences from the answer file
```

## Project layout

```
.claude/commands/npi.md     manager (slash command)
.claude/agents/             five station agents
npi/                        Python package: readers, stations, renderers, state
templates/                  document templates (docx, xlsx, Jinja)
config/                     people
input/                      sample cases and factory master data (read-only)
tests/                      pytest suite and fixtures
check_*.py                  architecture, template, quality, mutation and correction checks
```

## How it is developed

The project follows a document-driven workflow:

- `BRIEF.md`: what to build and the constraints (owned by the user)
- `VERIFY.md`: acceptance checklist per step (owned by the user)
- `TESTS.md`: tests expanded from VERIFY, each traced to its source
- `PLANS.md`: steps, decision tables and business rules
- `progress.md`: why each piece of work was done, measurements, issues, and the "Later" list
- `CLAUDE.md`: working rules for Claude Code (TDD, mutation testing, read-only reviews, batch gates)

Tests:

```bash
.venv/bin/pytest                      # full suite
.venv/bin/python check_quality.py     # content-depth scorecard
.venv/bin/python check_mutations.py   # mutation testing
```

## Status

Version 1 covers Batches 1–3: the full A0–C1 flow for fibre arrays and fan-out cables, BOM per the content-depth spec, and the unit cost sheet. Formal-spec depth, multi-sheet drawings and HTML emails (Batches 4–5) are not built; open items are listed under "Later" in `progress.md`.
