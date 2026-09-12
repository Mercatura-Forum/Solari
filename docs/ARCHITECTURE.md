# Architecture

Attribution: Thebes Core Team.

## 1. One state, pure modules, a trail in the same message

A firm contract (`motoko/main.mo`) is a persistent actor that holds one
`State` per concern in stable variables and does almost nothing itself: it
verifies the caller, then hands the verified principal, the caller's firm
authority and the chain time to a pure module. `Engine.mo` holds the
engagements: team and roles, imported trial balances, computed working papers,
the record kinds of the standards model and the trail. `Forms.mo`,
`Programme.mo`, `Disclosures.mo`, `Group.mo`, `Population.mo`, `Evidence.mo`,
`Signing.mo` and the connectors are pure modules over explicit state in the
same way. A pure module runs the same under the WASI test harness and on the
chain, which is what makes the batteries under `motoko/test/` proofs of the
contract rather than of a model of it.

Every accepted change appends its trail entry in the same message as the
change:

    hash = SHA-256(prev_hash | seq | at | by | action | target | payload_hash)

with a genesis `prev_hash` of sixty-four zeros. A change without a trail entry
cannot exist, because the message that made the change is the message that
wrote the entry, and a message on the substrate is atomic. Each stored target
carries the hash its trail entry committed to, so a changed target is detectable
as well as a changed entry. `verifyTrail` recomputes the chain and reports the
first break.

## 2. Refusal, not defaults

Every write returns `{ #ok : Json; #err : Text }`. A missing role, a phase that
would move backwards, a sign-off by the preparer of the version signed, an
immutable record kind asked to change, an account outside the chart, an amount
with more decimal places than the population allows, a computation input the
reference would reject: each is a refusal with its reason, and nothing is
written. The web application shows the reason; it never guesses.

## 3. The reference implementation is the oracle

Every figure the contract produces has a reference in `thebes-audit-standards`,
written independently in Python. `Dec.mo` reproduces the `decimal` module;
`Json.mo` writes the canonical serialisation the reference writes; `Csv.mo`
reads as `csv.reader` reads; `Dates.mo` computes calendar dates as `datetime`
does. The generators under `tools/` run the reference over its test cases and
write Motoko tests that require the contract's output to equal the reference's,
as canonical JSON, byte for byte. Journal-entry screening over a population of
millions of lines (`Population.mo`) is held to the same standard: its output is
the one-call output of `calc/Journals.mo`, itself byte-identical to the
reference, whatever the number of parts and steps it took.

## 4. Stated dates, chain time

A sign-off, a file assembly, a record: each carries the calendar date and time
stated by the person acting. The contract refuses a stated date earlier than
the latest already recorded in the engagement file, so a file cannot be
backdated past its own history, and refuses an assembly dated before the
auditor's report. Chain time orders the trail and is what session expiries and
outcall deadlines are compared against; it dates nothing.

## 5. Populations and evidence in stable memory

A journal-entry population is declared by the fingerprints of its parts, the
line count and the client file's SHA-256, then fed part by part; each part is
checked against its fingerprint and folded into accumulators bounded by the
chart of accounts on the heap and an entry index and the line text in a
stable-memory region. Screening runs in bounded steps against the 26 criteria,
an entry larger than a step carried across calls, so no single message ever
holds the population.

Evidence documents are fingerprinted, inspected, compressed and encrypted in
the browser. The contract stores the ciphertext in stable memory by fingerprint
and holds the file keys only as wraps to the registered devices of the people
entitled to them, in key rings with epochs: a ring whose current epoch reached
someone no longer entitled must be rotated before anything new is added under
it. Storage is append-only, as ISA 230 expects of an assembled file; erasure is
cryptographic, by destroying the wrapped key while the trail keeps the
fingerprint that proves the document existed. The store has a budget the firm
owner raises.

## 6. Connectors

The client's books can be read live in three ways, all of which end in the same
population machinery as a file import.

**Odoo through outcalls.** The contract names each request; the substrate's
validators fetch it independently and agree, at a declared quorum, on the parts
of the reply that participate in agreement; the contract takes each agreed
reply, stages the agreed pages in a region and says what to submit next. The
API key is kept only while the pull runs and is overwritten when it ends.

**The connector agent, route A.** `agent/` is a signed, read-only service that
runs beside the client's accounting system and serves the population line
schema over TLS it terminates itself, with adapters for Odoo, Tally (its XML
interface) and the Egyptian Tax Authority e-invoicing API. The contract pulls
pages at quorum, checks each page (exact count, ids strictly increasing across
pages), fingerprints it on the chain, recounts at the end and refuses a ledger
that changed during the pull. The credential is a one-time capability the
client's browser minted with their passkey; the agent refuses a second use.

**Route B.** For machines that must never be reachable, the agent writes the
population's pages, the balances and a manifest carrying every page's SHA-256
and its own signature; the contract verifies the signature against the agent's
registered key before a line is accepted.

Exchange rates are fetched from public sources, agreed by quorum per source and
reduced across independent publishers; a source that does not reach agreement
is recorded as such.

## 7. Electronic signatures

A person registers a signing passkey (WebAuthn, ES256). To sign, the contract
derives the hash of what is signed itself, issues a one-time challenge bound to
the contract, the target, the hash and a nonce, and accepts the browser's
assertion only if every part checks: the challenge, the origin, the relying
party id, user presence and user verification, and the P-256 signature over
`authenticatorData ‖ SHA-256(clientDataJSON)`, verified in `P256.mo`. The
accepted signature is recorded in the trail with everything needed to verify it
again off the chain.

## 8. Many firms

A firm is one contract; the service is many contracts and one registry
(`registry/main.mo` over the pure `Registry.mo`). The registry holds the firms
(id, contract id, name, the module hash the firm was activated with, status),
the operator's one-time invitations as the SHA-256 of the code, never the code,
and a membership index so the application can show a person their firms. It
holds no person's name, no client and no engagement: node operators read state.
Authority stays in each firm contract, which reports its memberships to the
registry after its own writes and keeps a backlog until the registry has
acknowledged.

A firm contract accepts a session only from a person who holds a role there;
`openSession` is the one exception and answers whether the caller is a member.
`tools/isolation_suite.py` probes every session method of a firm contract with
sessions from other firms and from strangers, and carries a negative control
that widens the gate on a scratch build and must go red, so the suite is known
to be able to fail.

The registry pins the release module. `provision_firm.py` installs a firm
contract, reads its module hash from every validator and activates the firm
only when the hash is the pinned one; `verify_fleet.py` repeats that check
across the fleet; `fleet_upgrade.py` rolls a release to one canary first. The
hash compared is the one the chain reports for the installed module, read from
every validator, and the tools stop on any divergence between validators.

## 9. Identity

Every user is their Memphis per-app principal, verified from an origin-scoped
session token. A firm contract verifies a token with Memphis once, on
`openSession`, and accepts it for queries until it expires; a token Memphis
cannot verify, including when Memphis cannot be reached, is refused. Until a
firm owner is named, the installing key may do two things only, set the web
origin and name the owner, and afterwards nothing.
