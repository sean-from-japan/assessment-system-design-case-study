# 1. The problem, and the requirements behind it

The coursework brief is not reproduced here. What follows is the problem as I
would state it from scratch, reconstructed from what the implementation
actually does.

## The situation

A university department sets, checks, sits and marks hundreds of assessments a
year. The process is not one person doing work; it is a **sequence of
approvals by different people**, and the reason it exists is that no single
person should be able to complete it alone.

That is the whole shape of the problem. The system is not a document store
with permissions bolted on. It is a workflow whose *point* is separation of
duties, and everything else is in service of that.

## Actors

Five distinct kinds of user, distinguished by what they may do rather than by
where they sit in the organisation:

| Actor | What they do |
|---|---|
| Academic | Writes assessments; checks other people's; marks; moderates |
| Teaching support | Administers the process: releases work, records deadlines, approves final marks |
| Exam officer | An additional approval stage for exams only |
| External examiner | Reviews exam papers from outside the department |
| Admin team | An administrative check on exam marks before moderation |

The important observation, and the one that shapes everything downstream:
**"academic" is not a permission.** The same academic is the setter of one
paper, the checker of another, and the moderator of a third. What they may do
depends on their relationship to *this* assessment, not on their job title.
Two of the five actors above are standing roles; the rest of the real
authority is per assessment.

## The three kinds of assessment

They share a beginning and an end, and differ in the middle:

- **Coursework** — specification written, checked, released to students,
  deadline passes, marked, moderated, marks approved.
- **In-semester test** — the same, except an autograded test skips marking
  entirely and returns results directly.
- **Exam** — the same, plus three extra approval stages: an exam officer, an
  external examiner, and a setter response to that examiner's feedback,
  followed by print, sitting, marking, an administrative check and moderation.

The exam path is roughly twice as long as the coursework path, and every extra
stage exists because a different person has to sign off.

## Requirements, as I would write them

**R1 — An assessment is always in exactly one known state.** Not a free-text
label; a value from a fixed set, per kind.

**R2 — State changes are the only way the process moves.** No field is edited
directly to skip a stage.

**R3 — Every transition names who may perform it,** either by role or by
relationship to that assessment. There is no transition anyone may perform.

**R4 — Separation of duties is enforced, not encouraged.** The setter cannot
approve their own work. The checker of a paper is not its moderator by
default. These are constraints, not conventions.

**R5 — Some transitions have domain preconditions** independent of who is
asking: a deadline cannot be recorded as passed before it has passed; team
marking is standardised before it begins.

**R6 — The interface shows what a user may do,** derived from the same rules
that enforce it, so the two cannot disagree.

**R7 — The audit question is answerable.** Who moved this assessment from
which state to which, and when.

**R8 — Users are staff, not students.** Everyone who logs in is a member of
staff; students are outside the system entirely. This narrows the threat model
usefully — but not to nothing, because separation of duties is precisely a
control against *authorised insiders*.

## What R8 means for security

It is tempting to conclude that a staff-only system needs weaker access
control. The opposite is true here.

If the only threat were an outsider, authentication alone would nearly do. But
the assessments this system holds contain **unreleased exam questions and
their answers**, and the process exists so that no one person can push a paper
through unreviewed. The person who would benefit from bypassing the workflow
is, almost by definition, someone with a legitimate account.

So the requirement is not "keep strangers out". It is **"an authenticated user
must not be able to do a thing the workflow says they may not do"** — which is
a much stronger requirement, and it is the one that
[the security review](05-security-review.md) finds the implementation does not
meet.
