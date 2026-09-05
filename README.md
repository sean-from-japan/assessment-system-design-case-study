# assessment-system-design-case-study

**English** | [日本語概要](README.ja.md)

A retrospective analysis of a multi-role assessment workflow system: what it
was meant to do, how it was built, where its security model fails, and what I
would build instead.

> **Attribution.** The original application was developed by a student team as
> university coursework. The university and the module are left out on purpose;
> ask me directly if you need them to verify this. This repository contains my
> independent retrospective analysis and does not claim sole authorship of the
> implementation. **No team source code is included here** — not copied, not
> edited, not paraphrased. Every diagram, table and line of code in this
> repository is my own work.

## What this is

Two halves.

**The analysis** ([`docs/`](docs/)) — the problem reconstructed from the
implementation, the architecture as built, the role model and workflow, the
data model, ten security findings with the evidence for each, and a redesign.

**The answer** ([`src/assessment_policy/`](src/assessment_policy/)) — a
working, tested implementation of the workflow and authorisation core, built
to make the largest finding structurally impossible. 672 tests.

## The system

A department sets, checks, sits and marks hundreds of assessments a year.
Coursework, in-semester tests and exams each move through a chain of
approvals by different people — setter, checker, exam officer, external
examiner, moderator, teaching support, admin team.

The point of the system is **separation of duties**. Four different people are
required to move an exam paper from draft to print. Everything else is in
service of that.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Draft
    Draft --> PendingChecker: setter submits
    PendingChecker --> PendingExamOfficer: checker approves
    PendingExamOfficer --> PendingExternal: exam officer approves
    PendingExternal --> PendingResponse: external examiner comments
    PendingResponse --> FinalCheck: setter responds
    FinalCheck --> SentToPrint: exam officer signs off
    SentToPrint --> Marking: exam sat
    Marking --> Moderation: admin check
    Moderation --> MarksApproved: moderator approves
    MarksApproved --> [*]
```

Built as a Spring Boot API and a React single-page application, with an
in-memory database and token authentication.

## The headline finding

The team modelled the domain correctly. Setter, checker, moderator and
external examiner are per-assessment relationships in the schema, not roles,
and the permission checks that exist compare the caller against *this
assessment's* checker. Whoever wrote those understood the problem.

**The workflow service has two methods.** One computes which actions are
available to a user — carefully, consulting both their role and their
relationship to the assessment. The other performs a transition, and **takes
no user at all**. The controller receives the authenticated principal and does
not pass it on.

So the careful authorisation logic decides **what to render**, and the endpoint
that changes the state enforces nothing beyond "you are logged in". Any
authenticated staff member can approve a paper they are not the checker of, or
send an exam to print.

Across 45 endpoints there are **zero** method-level authorisation annotations —
with method security switched on in the configuration. Nine of the ten findings
have that same shape: **a control that exists in one layer and is missing in
the layer that enforces it.**

Full evidence: [security review](docs/05-security-review.md).

## The ten findings

| | Finding | Severity if deployed |
|---|---|---|
| F1 | Account creation is unauthenticated and the caller picks the role | Critical |
| F2 | The workflow endpoint performs no authorisation at all | Critical |
| F3 | Permission checks read their facts from the request body | Critical |
| F4 | The database console is reachable without authentication | High |
| F5 | Most endpoints have no authorisation beyond "logged in" | High |
| F6 | Tokens are stored where any script on the page can read them | Medium |
| F7 | Credentials in configuration and in a source comment | Medium |
| F8 | The signing key is packaged inside the application artifact | Medium |
| F9 | Roles are compared by substring over a delimited string | Low, latent |
| F10 | Tokens cannot be revoked | Low |

**Also worth stating:** passwords are hashed with bcrypt and excluded from
serialisation, the signing is asymmetric rather than a shared secret, and the
private key was deliberately kept out of version control. I went in expecting
to find a committed private key and did not. That expectation was wrong, and
[F8](docs/05-security-review.md#f8--the-signing-key-is-packaged-with-the-application)
says so.

## The redesign

The findings are not ten independent bugs. They are one decision —
**authorisation is something each endpoint remembers to do** — and nine
consequences. So the fix is not to add the missing checks. It is to make the
missing check impossible to write.

**One table describes every legal transition and who may perform it, and every
question the system asks is answered from that table.** Not "the same rules" —
the same table, at runtime.

```python
from assessment_policy.engine import WorkflowEngine
from assessment_policy.model import Action

engine.perform(assessment_id, actor, Action.APPROVE)
# Forbidden: staff 1 (academic) may not approve this exam:
#            that requires checker
```

Five decisions, each closing a specific finding:

| Decision | Closes |
|---|---|
| The actor is a required parameter of `perform` — there is no overload without one | F2 |
| Nothing about the assessment comes from the caller; the record is read from the store | F3 |
| Roles are an enumerated set; relationships are derived per assessment | F9 |
| A transition with no roles and no relationships is a **test failure** | F5 |
| Permission and precondition are different refusals, so a blocked action can explain itself | — |

The property that matters is asserted exhaustively — for every kind, state,
actor and action, **being offered an action and being allowed to perform it
are the same thing**:

```python
offered = {a.action for a in engine.available_actions(id, actor) if a.enabled}
accepted = {action for action in Action if perform_succeeds(action)}
assert offered == accepted
```

On the audited system that test fails for every state where the interface hid
an action the API still allowed. See
[`tests/test_no_drift.py`](tests/test_no_drift.py) and
[what I would change](docs/06-what-i-would-change.md).

## Read in this order

| | |
|---|---|
| [1. The problem and requirements](docs/01-problem-and-requirements.md) | Reconstructed from the implementation; why a staff-only system needs *stronger* access control, not weaker |
| [2. Architecture as built](docs/02-architecture.md) | Layering, the request path, and the numbers |
| [3. Roles and workflow](docs/03-roles-and-workflow.md) | Roles against relationships; the two disagreeing state machines |
| [4. The data model](docs/04-data-model.md) | What the schema gets right, and the missing audit log |
| [5. Security review](docs/05-security-review.md) | Ten findings with evidence, and what was done well |
| [6. What I would build instead](docs/06-what-i-would-change.md) | The five design decisions, and the tests that hold them |
| [7. Method and limits](docs/07-method-and-limits.md) | How I read it, what I did not verify, and why |

## Running the redesign

Python 3.9 or newer. No runtime dependencies.

```bash
git clone https://github.com/sean-from-japan/assessment-system-design-case-study.git
cd assessment-system-design-case-study
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e . && pip install -r requirements-dev.txt
pytest        # 672 tests
ruff check .
```

## Limits of this analysis

I read the implementation; I did not run it — the signing key it needs is not
in the snapshot, deliberately excluded from version control. Two findings are
therefore stated as expectations rather than facts, and marked as such in
[document 7](docs/07-method-and-limits.md).

The redesign is the workflow and authorisation core only. There is no web
layer, no database and no frontend: authentication, token storage and key
management are argued for in the review and not implemented.

This was coursework, built by six people in one semester, running on a laptop
against an in-memory database with no real users and no real exam papers. The
findings are recorded as things to understand, and several are mistakes I
would have made. A few, I did.

The module mark was 54/100 — context for what the review says, not a headline.

## Licence

MIT — see [LICENSE](LICENSE). Covers the analysis and the code in this
repository, all of which is my own work. It does not extend to the original
system, which is not included here.
