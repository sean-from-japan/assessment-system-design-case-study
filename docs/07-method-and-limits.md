# 7. Method, and the limits of this analysis

## What I did

I read the implementation: the backend Java sources, the frontend components,
the build and configuration files, and the tests. I traced the paths that
matter — authentication, authorisation, and the workflow — and drew the role
model, the state machines, the data model and the request path from what the
code does rather than from any document.

I then wrote the engine in this repository as a concrete answer to the largest
finding, and wrote the tests that would have caught it.

## What I did not do

**I did not run the application.** The signing key it needs is not in the
snapshot I read — deliberately excluded from version control, see F8 — so it
does not start without generating a key pair, and the case study did not need
me to. Every finding here is from reading, and the two places where that
limitation bites are marked below.

**I did not test a running system.** No requests were sent, no console was
opened, no token was forged. The findings describe what the code permits, not
an exploitation of it.

**I did not read the coursework brief while writing this.** The requirements
in [document 1](01-problem-and-requirements.md) are reconstructed from the
implementation on purpose: the exercise was to work out what a system is meant
to do by reading what it does.

## Where reading is not enough

Two things I state with less confidence than the rest, and both are flagged
where they appear:

**Two endpoints declare two request bodies each.** The status-change endpoints
for exams and tests each take two parameters annotated as the request body.
A framework can bind only one. I expect these endpoints to fail at runtime, and
that the feature was never exercised — which is consistent with there being no
controller tests. I did not confirm it by execution.

**Two endpoints share a URL pattern.** Two handlers map to the same path shape,
differing only in the name of the path variable — which is not part of the
mapping. I expect this to be rejected when the application starts. If it is,
the application in this snapshot does not run at all, which would be a
striking thing to be true of a submitted project; that is precisely why I am
not asserting it.

Both are the kind of claim that a five-minute run would settle. I would rather
say that than imply I had.

## What the tests told me

The test suite is 15 backend test methods across two service classes, plus a
context-load test, and one frontend test that is the **unmodified project
template** — it asserts the presence of text from the framework's starter page,
which this application does not render. It would fail if run.

The 15 that exist are competent: mocked repositories, checking that permission
failures raise and that the service methods behave. They test the layer where
the checks *are*, which is why they pass.

There are **no controller tests and no security tests**. That is not a
coincidence — it is the same fact as the review. Every serious finding lives in
a layer nobody wrote a test for, and the two most likely-broken endpoints are
in the same layer. The shape of the test suite predicts the shape of the
findings almost exactly.

## Attribution and scope

The system was built by a six-person student team as university coursework over
one semester. I was one of them. The university and the module are left out on
purpose; ask me directly if you need them to verify this. **This
analysis is mine; the implementation is the team's, and I do not claim sole
authorship of it.** I have not attributed any individual finding to any
individual person, because I cannot and because it would not be useful.

The findings are recorded as things to understand. A coursework project on a
laptop, with an in-memory database and no real users, is not a deployed system,
and several of the findings are mistakes I would have made — a few, I did.

The module mark was 54/100. I mention it once, here, because it is context for
what the review says rather than a headline: it is consistent with a project
whose domain model was understood and whose implementation did not hold
together, which is what reading it two semesters later shows.

## What is not in this repository

No team source code, in any form — not copied, not edited, not paraphrased into
equivalent code. No project README, no testing report, no coursework
specification, no university branding, no names, no credentials, no
configuration files. Every diagram is redrawn by me, every table is written
from my own reading, and every line of code in `src/` and `tests/` was written
for this repository.

Descriptions in these documents name components by what they do — "the workflow
service", "the security configuration" — rather than reproducing package or
class names, and no code is quoted.
