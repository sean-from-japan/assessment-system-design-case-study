# 5. Security review

Findings from reading the implementation. Each one states what I **observed**,
what follows from it, and how I would fix it. Where I could not confirm
something by execution, that is said explicitly rather than smoothed over.

This is a student coursework project that ran on a laptop against an in-memory
database. Nothing here was ever exposed to real users or real exam papers, and
the findings are recorded as things to understand, not as failures to hold
against anyone. Several of them are mistakes I would have made.

| | Finding | Severity in a deployed system |
|---|---|---|
| F1 | Anyone can create an account and choose its role | Critical |
| F2 | The workflow endpoint performs no authorisation at all | Critical |
| F3 | Permission checks read their facts from the request body | Critical |
| F4 | The database console is exposed without authentication | High |
| F5 | Most endpoints have no authorisation beyond "logged in" | High |
| F6 | Tokens are stored where any script on the page can read them | Medium |
| F7 | Credentials in configuration and in a source comment | Medium |
| F8 | The signing key is packaged with the application | Medium |
| F9 | Roles are compared by substring | Low, latent |
| F10 | Tokens cannot be revoked | Low |

---

## F1 — Anyone can create an account and choose its role

**Observed.** The account creation endpoint is on the list of paths permitted
without authentication, alongside login. Its request body carries a username,
a password **and a role**, and the role is written to the new staff record as
supplied.

The service that creates staff *does* check permission: it requires the caller
to be an exam officer or teaching support. The endpoint satisfies that check by
**constructing an authentication object in code** — an invented user with a
hard-coded name and the exam officer role — and passing it in place of the real
caller.

**Why this is the worst one.** The authorisation check exists, is correct, and
is defeated by the only caller that reaches it. An anonymous request creates an
exam officer and receives a valid token for it in the response.

Every other finding is then reachable from an account the attacker made
themselves. And the account is indistinguishable, afterwards, from one the
department created.

**Fix.** Account creation requires an authenticated caller with the right role,
enforced by the framework rather than by hand. The role is never taken from the
request. If self-service sign-up is genuinely wanted, it creates an account
with the lowest privilege and no role at all, pending approval.

---

## F2 — The workflow endpoint performs no authorisation at all

**Observed.** The workflow service has two methods: one computes the actions
available to a user, consulting their role and their relationship to the
assessment; the other performs a transition and **takes no user**. The
controller receives the authenticated principal and does not pass it on.

**Consequence.** Any authenticated user can drive any assessment through any
transition that is legal for its current state: approve a paper they are not
the checker of, submit feedback as the external examiner, send an exam to
print. Separation of duties — the reason the system exists — is not enforced on
this path.

The careful role logic in the other method is computing what to render.

**Fix.** One code path. The method that answers "what may this user do" and the
method that performs the action must consult the same table, and the performing
method must take the actor. This is what
[the redesign](../src/assessment_policy/engine.py) does, and
[`test_no_drift.py`](../tests/test_no_drift.py) asserts the two can never
diverge, for every state, actor and action.

---

## F3 — Permission checks read their facts from the request body

**Observed.** The controller-inline status endpoints branch on the status of
the assessment **as sent in the request body**, and compare the caller's
username against the checker and moderator **from that same body**, rather than
against the stored record.

**Consequence.** The caller supplies the facts their own permission check is
evaluated against. A request can present an assessment as being in the state
whose transition the caller wants, and nominate the caller as its checker, in
the body that is then checked and saved.

This is a more general failure than F2. F2 forgot to check; F3 checks
diligently against attacker-controlled input.

**Fix.** Load the record by id from the store. Take from the request only the
identifier and the action. Never trust a client-supplied state or a
client-supplied relationship — in the redesign here, the engine's `perform`
takes an id, an actor and an action, and there is nowhere for a state to be
passed in.

---

## F4 — The database console is exposed without authentication

**Observed.** The web console for the in-memory database is enabled, mapped to
a path, and that path is on the permitted-without-authentication list. Frame
protection is disabled globally so the console can render in a frame. The
database username and password are in the same configuration file.

**Consequence.** An unauthenticated request to that path reaches a full SQL
console over the live database: read every exam question and answer, and write
whatever it likes.

The disabled frame protection is a second, separate cost: it removes
clickjacking protection from every page of the application, not just the
console.

**Fix.** The console is a development convenience. It belongs behind a
development-only profile that is not built into the deployed artifact. Frame
protection stays on; if a development tool needs a frame, the exception is
scoped to that path.

---

## F5 — Most endpoints have no authorisation beyond "logged in"

**Observed.** The filter chain's only rule, after the permitted paths, is that
a request must be authenticated. Method security is **enabled** in the
configuration, and across 45 endpoints there are **zero** authorisation
annotations. Every permission decision that exists is hand-written inside a
method body, and many methods have none.

Endpoints that check nothing include: list every staff member, fetch any
assessment by id, delete any assessment, update any coursework, exam or test.

**Consequence.** Any authenticated user can read every assessment in the
department, including unreleased exam papers with their answers, and can delete
any of them.

**Why it is easy to miss.** Enabling method security and then not using it is
worse than not enabling it. The configuration says authorisation is handled;
the absence of a single annotation looks like a default rather than a gap.

**Fix.** Deny by default. Every endpoint carries an explicit rule, and a test
enumerates the endpoints to assert that none is missing one. That test is
cheap and it is the one that would have caught this whole class.

---

## F6 — Tokens are stored where any script on the page can read them

**Observed.** On login, the token and the full user record are written to
browser local storage, and read back on start-up. Thirteen references across
the frontend.

**Consequence.** Any script executing on the page can read the token and use
it until it expires. This is only reachable through a cross-site scripting
flaw, and I found no obvious injection point in this frontend — the risk is
that a token in local storage converts *any* future XSS into a full account
takeover, rather than a contained defect.

**Fix.** A `HttpOnly`, `Secure`, `SameSite` cookie, which script cannot read.
That reintroduces the need for CSRF protection, which the application
currently switches off — the two decisions have to be made together, and the
review of this trade-off is itself the answer to the coursework's security
question.

**Caveat.** For a system with no cross-origin surface and a two-hour token,
this is the lowest-cost finding to live with. I would fix F1 to F5 first.

---

## F7 — Credentials in configuration and in a source comment

**Observed.** The application configuration contains a database password and a
default administrator username and password. The same administrator
credentials also appear as a **comment at the bottom of the security
configuration class**. The start-up seeder creates fourteen staff accounts with
hard-coded weak passwords.

**Consequence.** For a demonstration this is deliberate and reasonable. The
problem is what it becomes: a seeded administrator account with a known
password is the account that survives into a deployment, and credentials in a
comment survive every configuration change made afterwards.

**Fix.** Seed data belongs behind a development profile. Secrets come from the
environment. The comment is deleted — and, since it has been in version
control, the credential is treated as disclosed and rotated.

---

## F8 — The signing key is packaged with the application

**Observed, with a correction.** The token signing key pair is loaded from the
application's classpath, from a path given in the configuration.

I expected to find the private key committed. **It is not.** The repository's
ignore file excludes the key directory, and no key files are present in the
snapshot I read. That expectation was wrong and the implementation is better
than I assumed.

What remains is the design: the private key is loaded as a **classpath
resource**, which means the deployed artifact contains it. Anyone who can read
the built application can sign tokens for any user with any role. The
application also fails to start without it, so the key has to travel with the
build.

The exclusion also has a practical cost the team will have felt: a fresh clone
does not start, and there is no key generation step. That is very likely why
this snapshot has no keys.

**Fix.** Load the key from outside the artifact — an environment variable, a
mounted file, a secret manager. Add a documented command to generate a
development pair, so a clean clone starts.

**Not verified by execution.** I did not run the application, precisely
because the key material is absent. Everything in this finding is from
reading.

---

## F9 — Roles are compared by substring

**Observed.** Roles are stored in a single delimited text field, and nineteen
checks ask whether it *contains* a role name.

**Consequence.** Today, no role name is a substring of another, so this is
**latent, not live**. It means the safety of the permission model rests on an
accident of naming: adding a role whose name contains an existing one grants
that existing one silently, everywhere, with no code change.

Compounding it, exam officer status exists both in this string and as a
separate boolean column, written and read by different code paths with nothing
keeping them consistent.

**Fix.** Roles become a set of enumerated values, compared by equality. One
representation for exam officer. In the redesign here, `Actor` rejects a role
that is not a member of the enumeration, so a string cannot be smuggled in.

---

## F10 — Tokens cannot be revoked

**Observed.** Tokens are signed, self-contained and valid for two hours. There
is no deny list and no server-side session. Logout clears browser storage
only.

**Consequence.** A token stays valid for up to two hours after the account is
deleted, its role is downgraded, or the user logs out. Combined with the
staff-deletion behaviour, an account can be deleted from the database and its
token keep working.

**Fix.** For a system this size, shorter tokens plus a refresh token that can
be revoked. A revocation list keyed on token identifier is the smaller change
if the token lifetime has to stay.

---

## What was done well

Worth stating, because a review that only lists faults is not an accurate
description of the code.

- **Passwords are hashed with bcrypt**, and excluded from serialisation, so
  they do not leak through endpoints that return whole staff records. Both
  halves. This is the finding I most expected to make and did not.
- **The domain model is right.** Setter, checker, moderator and external
  examiner are modelled as per-assessment relationships, and the permission
  checks that do exist correctly compare the caller against the assessment's
  own checker rather than against a role. Whoever wrote those understood the
  problem.
- **Asymmetric signing.** A public/private key pair rather than a shared
  secret, which means a verifying service never needs the signing key. That is
  a better default than most projects this size choose.
- **The private key was excluded from version control** — deliberately, in the
  ignore file. Given how many student projects commit key material, this was
  done on purpose and it worked.
- **Stateless authentication with CSRF disabled** is a defensible pairing
  while the token travels in an `Authorization` header. It stops being
  defensible if F6 is fixed by moving to cookies, and those two decisions have
  to move together.

## The pattern underneath

Nine of the ten findings share one shape: **a control that exists in one layer
and is missing in the layer that enforces it.**

The role logic exists — in the method that decides what to render. The
permission check on staff creation exists — and is handed a fabricated caller.
The relationship model exists in the schema — and the check reads the
relationship from the request body. The key is kept out of version control —
and loaded from the artifact.

This is not carelessness. It is what happens when authorisation is a thing you
remember to write rather than a thing the structure requires. Six people, a
deadline, an endpoint each: everyone checks what they are thinking about, and
the endpoints nobody was thinking about have nothing.

The fix is structural, and it is [the next document](06-what-i-would-change.md).
