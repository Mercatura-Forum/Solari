# Solari: Thebes Protocol Audit System

**Solari is an audit system for audit firms that runs as a smart contract on the
Thebes substrate.** Every engagement is a file whose every change is an entry
in a hash-chained trail; every figure is the output of a specified computation
under the International Standards on Auditing that reproduces its published
reference byte for byte; every sign-off, working paper and evidence document is
an object a third party can verify against the chain's own commitment. Web
application in English and Arabic; connector agent in Rust for the client's
accounting system. Written in Motoko. Apache 2.0.

- **A trail, not a database.** Every accepted change appends to the engagement's
  hash chain in the same message; `verifyTrail` recomputes it and locates the
  first break.
- **Figures that reproduce.** Materiality (ISA 320, 600), sampling (ISA 530),
  analytical review (ISA 520), misstatement aggregation (ISA 450) and
  journal-entry testing against 26 stated criteria, byte-identical to the
  reference implementation in `thebes-audit-standards`.
- **Books read live.** Seven trial-balance sources; Odoo through the substrate's
  HTTP outcalls at a declared validator quorum; any system through a signed
  connector agent; Tally and the Egyptian Tax Authority e-invoicing.
- **Signed by people, not accounts.** Passkey sign-offs, four-eyes on every
  form, documents encrypted in the browser and stored by fingerprint with keys
  wrapped to registered devices.
- **Many firms on one service.** One contract per firm from a registry that pins
  the release every firm runs; isolation proven method by method.

| | |
|---|---|
| Standards | ISA 220, 230, 240, 260, 265, 300, 315, 320, 330, 450, 505, 520, 530, 560, 570, 580, 600, 700; ISQM 1, 2 |
| Forms | fourteen forms of the audit cycle, 120 procedures, sixteen record kinds; PDF, Word and Excel in English and Arabic |
| Sources | spreadsheet, QuickBooks Online, Sage 50, SAP FAGL, Odoo, ETA e-invoices, `thebes-ledger-core` with inclusion proofs |
| Identity | Memphis passkeys; no wallets, no seed phrases |
| Status | live on a Thebes network for a demonstration firm and a first audit firm; not independently audited |

Solari is written in Motoko for the Thebes substrate, with a web application in
English and Arabic on the Thebes SDK and a connector agent in Rust that runs
beside the client's accounting system. Its computations follow the
International Standards on Auditing, each stated where it is used; their
reference implementation and test vectors are published in
[`thebes-audit-standards`](https://github.com/Mercatura-Forum/thebes-audit-standards).
No model participates in the evidence chain.

**Type-safe, memory-safe, no silent errors.** Motoko is a strongly and
statically typed language of the ML family, the family whose members run the
trading and risk systems of some of the world's largest financial institutions.
It has option types in place of nulls, arbitrary-precision and overflow-checked
arithmetic that traps rather than wraps, garbage-collected memory with no
pointers to corrupt, and atomic message execution: a trap rolls the whole
message back. Solari is written to that discipline throughout. Every refusal is
a typed `Result` value with its reason (a missing role, a phase that cannot move
backwards, a stated date before the file's own history, an account outside the
chart), never a default silently applied; decimal arithmetic is exact, with the
semantics of the reference implementation, and a computation that cannot be
made exact is refused rather than rounded into agreement; a read that would be
unbounded is paged, never truncated.

## Why it runs on Thebes

An audit file is the record of what the auditor examined, when, on what
evidence, and who signed. Running it as a smart contract on the Thebes
substrate changes what that record is:

- **Redundant by construction.** The contract does not run on a server; it runs
  on every validator of the network, and its state is what a Byzantine
  fault-tolerant quorum of them agrees on. There is no primary to fail over
  from and no replica to fall behind: every validator holds the same
  engagements, the same working papers and the same trail, and a validator
  that is lost is replaced by the others without a restore.

- **Tamper-proof execution.** A sign-off, a working paper or a record exists
  only if the validators executed the same call on the same state and reached
  the same result. No administrator, no operator of a single machine and no
  validator on its own can alter a figure, back-date a sign-off or remove an
  entry: every accepted change appends to the hash-chained trail in the same
  message, and the state every validator holds is itself hashed and compared at
  every height.

- **Verification and proofs.** `verifyTrail` recomputes an engagement's chain
  and locates the first break; every working paper carries the fingerprint of
  its input; every imported population carries its source's SHA-256; a signed
  export from the connector agent is verified against the agent's registered
  key before a line of it is accepted; a trial balance from `thebes-ledger-core`
  arrives with per-line inclusion proofs. A regulator, a quality reviewer or a
  successor auditor verifies the file against the chain's own commitment, not
  against the firm's word.

- **A profession's infrastructure, not a vendor's.** The validators of a Thebes
  network can be run by the institutions themselves: audit firms, the
  professional body, the regulator, the tax authority, as a consortium subnet.
  The files then live on infrastructure the profession jointly operates and
  jointly verifies, with every member able to prove the state to itself,
  rather than on a system one vendor owns and the rest must trust.

- **Upgrades that keep the record.** The contract is upgraded in place, its
  state carried across, and the batteries prove the state survives. A file is
  never migrated, exported or re-keyed: the chain it was written on is the
  chain it stays on.

- **Evidence that never leaves the firm in clear.** Evidence documents are
  compressed and encrypted in the browser; the contract holds ciphertext and
  keys wrapped to the team's registered devices. No plaintext byte and no
  usable key ever reaches the chain.

## What is here

| Layer | What it does |
|---|---|
| **Firms and identity** | Many firms on one service, one contract per firm, created from one-time invitations; a registry pins the release module every firm contract runs and holds each person's memberships; a firm contract accepts a session only from a person who holds a role there. Every user is their Memphis per-app principal, verified from an origin-scoped session token; all authority is keyed on it. |
| **Engagements and the trail** | Engagements with their teams (partner, manager, senior, staff, engagement quality reviewer, client) and forward-only phases; every accepted change appends `SHA-256(prev │ seq │ at │ by │ action │ target │ payload_hash)` in the same message, and `verifyTrail` recomputes the chain. Event dates are stated by the person signing and can never precede the file's own history. |
| **Trial balance import** | Seven source systems (generic spreadsheet, QuickBooks Online, Sage 50, SAP FAGL, Odoo, Egyptian Tax Authority e-invoice documents, `thebes-ledger-core` with per-line inclusion proofs), each import recording the source's SHA-256 and an evidence grade; accounts outside the chart are reported, never bucketed. |
| **Connectors** | The client's books read live: Odoo through the substrate's HTTP outcalls with a declared quorum of validators agreeing on every reply; any system through the connector agent, a signed, read-only service beside the client's system with adapters for Odoo, Tally and the Egyptian Tax Authority e-invoicing API, pulled by the contract or delivered as a signed export for machines that must never be reachable; exchange rates from public sources, agreed by quorum and reduced across independent publishers. |
| **Computations** | ISA 320 and 600 materiality; ISA 530 monetary-unit and attribute sampling; ISA 520 analytical review; ISA 315 trend expectation; ISA 450 misstatement aggregation with rollover and iron-curtain effects; ISA 330/700 tie-out; ISA 570 going concern; digit analysis; ISA 240 journal-entry testing. Each run is a working paper carrying the fingerprint of its input. |
| **Journal-entry testing** | The whole population, imported in parts and screened in bounded steps against 26 stated criteria, every flagged entry naming its rules; byte-identical to the reference over millions of lines. |
| **Forms, programme, disclosures, group** | The fourteen forms of the audit cycle with pre-fill, staleness after signing and four-eyes sign-off; every one of the 120 procedures with its derived state and reviewed conclusion; a catalogue of 74 disclosure requirements scoped to the engagement; components and component auditors under ISA 600. The file is not assembled while any of them is short. |
| **Records and file assembly** | The sixteen record kinds of the standards model, validated against their declared fields, immutable kinds refusing change; assembly by a partner after the completion form is approved, with the sixty-day deadline, the object count and the trail head recorded, and only post-assembly change records accepted afterwards. |
| **Evidence and signatures** | Documents fingerprinted, inspected, compressed and encrypted in the browser, stored by fingerprint in stable memory with keys wrapped to registered devices; electronic signatures by passkey (WebAuthn, ES256) over one-time challenges the contract verifies itself, recorded in the trail with everything needed to verify them again. |
| **Client portal and read API** | A client sees exactly what the contract's client-scoped queries let them see; an OpenAPI 3.1 read API over keyed routes with declared scopes, served by the contract itself. |

The forms: client acceptance and continuance (ISQM 1, ISA 220, ISA 210, IESBA
Code), engagement letter (ISA 210), planning memorandum (ISA 300), risk
assessment register (ISA 315, ISA 330), engagement team discussion and fraud
risk (ISA 240, ISA 315), materiality (ISA 320), sampling plan and evaluation
(ISA 530), external confirmations (ISA 505), going concern (ISA 570), summary of
misstatements (ISA 450), subsequent events (ISA 560), management representation
letter (ISA 580), letter to those charged with governance (ISA 260, ISA 265),
completion and sign-off (ISA 220, ISA 230, ISA 700, ISQM 2). Each exports to
PDF, Word and Excel, in English or Arabic, right-to-left in Arabic.

## Layout

```
motoko/
  main.mo                 the firm contract (persistent actor)
  registry/main.mo        the firm registry contract
  src/Engine.mo           engagements, roles, papers, records, trail
  src/Forms.mo            forms, sign-off, staleness, file assembly
  src/Programme.mo        the audit programme
  src/Disclosures.mo      the disclosure checklist
  src/Group.mo            the group audit
  src/Population.mo       journal-entry populations in parts, screened in bounded steps
  src/Evidence.mo         evidence documents: ciphertext, wrapped keys, devices
  src/Signing.mo, P256.mo electronic signatures by passkey and their verification
  src/Registry.mo         the firm registry (pure module)
  src/Odoo.mo, Rates.mo   connectors through HTTP outcalls
  src/AgentPull.mo        route A of the connector agent
  src/RouteB.mo           route B: the signed export
  src/Api.mo              the read API and its OpenAPI description
  src/TbImport.mo, Csv.mo trial-balance import
  src/Dec.mo, Json.mo     exact decimal arithmetic; JSON value, parser, canonical writer
  src/calc/*.mo           the computations
  src/Seed.mo             the standards model (generated)
  src/FormsSeed.mo        the forms (generated)
  test/                   the battery, run under WASI
agent/                    the connector agent (Rust): Odoo, Tally, ETA e-invoicing adapters
forms/                    the fourteen form definitions (generated)
frontend/                 the web application (React, Vite, Tailwind, Thebes SDK);
                          public/config.js carries a deployment's contract ids
tools/                    generators, oracle harnesses, the fleet tools, the end-to-end runs
registry/                 the registry's manifest
docs/                     the architecture overview
```

## Building and testing

Requirements: the Thebes Motoko compiler (Motoko 1.4.1 with the substrate's
HTTP outcall primitives, which `src/Http.mo` uses) for the firm contract; stock
`moc` 1.4.1 builds the registry contract and the battery; `mops`; `wasmtime`
for the battery; Python 3 for the generators and oracle harnesses; Node for the
web application; Rust for the agent. The manifests take the compiler from
`MOC`.

```sh
cd motoko && mops install
$MOC --legacy-persistence $(mops sources) -o ../build/audit.wasm main.mo
moc --legacy-persistence $(mops sources) -o ../build/registry.wasm registry/main.mo
./test/run.sh                              # every test must print a non-zero count of what it examined
python3 tools/gen_dec_cases.py && python3 tools/gen_calc_cases.py && python3 tools/gen_import_cases.py
cd agent && cargo test
cd frontend && npm install && npm run build
```

The generators take the reference implementation from `AUDIT_STANDARDS` (a
checkout of `thebes-audit-standards`, by default beside this repository). The
oracle tests compare every output as canonical JSON, byte for byte: the
decimal module against Python `decimal`, the computations against
`computations/`, the importer against `tools/tb_import.py`, the CSV reader
against `csv.reader`, SHA-256 against `hashlib`, the journal-entry screening
against `computations/journals.py`, the connector mappings against their
recorded replies.

The contracts are built with legacy (classical) persistence so that an in-place
upgrade keeps their state. The fleet tools provision a firm from an invitation,
verify every firm contract on every validator against the pinned release, roll
a release canary-first, and prove that a session from one firm is refused by
every other, with a negative control that must go red.

## Design

`docs/ARCHITECTURE.md` describes the engagement model, the trail, the
stated-date rule, the population and evidence stores, the connectors, the
many-firms registry and how each part is proven.

## Licence

Apache License 2.0 (see `LICENSE`). The vendored Thebes SDK under
`frontend/vendor/@thebes/sdk` carries its own notice.

Attribution: Thebes Core Team.
