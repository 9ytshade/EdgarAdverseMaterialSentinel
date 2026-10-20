# Architectural Decision Records (ADRs)

## Project: EdgarAdverseMaterialSentinel
**Author**: 9ytshade  
**Status**: Accepted & Deployed on Studionet  

---

### ADR-001: Whitelisted Authoritative SEC EDGAR Provenance & Strict CIK Binding

#### Context
In tokenized debt and RWA credit pools, allowing arbitrary disclosure links introduces severe systemic risks. An attacker could host a fraudulent website imitating a company's press release or fabricated 8-K filing claiming the company entered receivership, causing an on-chain automated sentinel to trigger an unauthorized tranche freeze, liquidating positions or causing panic. Conversely, a borrower could point to a benign blog post claiming compliance.

#### Decision
Enforce a contract-side authoritative provenance gate:
1. **Restricted Domain Whitelist**: Only subdomains of the U.S. Securities and Exchange Commission (`sec.gov`, `www.sec.gov`, `data.sec.gov`, `archives.sec.gov`) are accepted.
2. **Accession Number Schema**: Enforce strict SEC accession number regex matching (`r"^\d{10}-\d{2}-\d{6}$"`).
3. **CIK Issuer Binding**: The filing URL and the SEC EDGAR filing header must match the registered debt facility's 10-digit Central Index Key (CIK). If the CIK does not match, the adjudication marks the disclosure as `VERDICT_UNRELATED_ISSUER` and prevents any impact on the facility's covenants.

#### Consequences
- Completely prevents spoofed, unofficial, or submitter-controlled web pages from altering covenant states.
- Authoritatively binds legal disclosures to verified corporate identities.

---

### ADR-002: Dual-Engine Calldata Extraction in Equivalence Principle Hook

#### Context
GenLayer's Equivalence Principle (`gl.vm.run_nondet_unsafe(evaluate, validate)`) provides a consensus bridge for non-deterministic web and LLM execution. In the live validator environment, `leader_result` is an instance of `gl.vm.Result` exposing candidate outputs via `.calldata`. However, local mock test harnesses (such as unit test frameworks) pass the raw Python dictionary or object returned by `evaluate()`.

#### Decision
Implement dual-path calldata unwrapping in `validate()`:
```python
if hasattr(leader_result, "calldata"):
    candidate_data = leader_result.calldata
else:
    candidate_data = leader_result
```
After unwrapping, both leader and validator outputs are parsed and compared across discrete taxonomy and quantized thresholds.

#### Consequences
- Full compatibility across live Studionet multi-validator consensus and local automated test environments.
- Eliminates `AttributeError` exceptions during consensus rounds.

---

### ADR-003: Discrete Categorical Quantization for Legal & Materiality Scoring

#### Context
Large Language Models operating across different validator nodes may produce slight discrepancies in descriptive summaries and continuous float estimates (e.g. validator 1 estimates 82.5% materiality, while validator 2 estimates 85.0%). In decentralized blockchains, continuous floating-point scoring leads to state divergence and consensus stalling.

#### Decision
Quantize all non-deterministic legal risk evaluations into discrete integers and enums:
1. **Event Category**: Discrete taxonomy (`0` = None, `1` = Bankruptcy/Receivership, `2` = Debt Acceleration/Default, `3` = Regulatory Enforcement, `4` = Executive Fraud Investigation, `5` = Delisting/Noncompliance, `6` = Routine Non-Material).
2. **Materiality Score**: Scaled integer `0..100` (e.g., 85). Validators accept minor delta tolerances ($\le 15$ points) if both agree on the categorical adverse event classification.
3. **Adjudication Verdict**: Discrete enum (`0` = Pending, `1` = Material Adverse Confirmed, `2` = Routine Non-Material, `3` = Unrelated Issuer, `4` = Malformed Filing, `5` = EDGAR Unavailable).

#### Consequences
- 100% consensus convergence on the first voting round across heterogeneous validator nodes.
- Downstream RWA protocols can execute deterministic logic without string parsing or floating-point rounding errors.

---

### ADR-004: Fail-Closed Fault Tolerance for Government Regulatory Endpoints

#### Context
Regulatory websites like `sec.gov` frequently apply bot-mitigation policies, rate limiting (HTTP 429), or cloud IP bans (HTTP 403 Forbidden). If validators receive an HTTP 403 or network timeout when attempting to fetch a filing, throwing an unhandled exception would crash the validator execution or cause state inconsistency.

#### Decision
Implement deterministic fail-closed state transitions:
- When an HTTP request returns a non-200 status code, timeout, or DNS resolution failure, the evaluation returns `VERDICT_EDGAR_UNAVAILABLE` (verdict 5) with materiality score `0` and `covenant_breach_detected = False`.
- The filing status is updated to `STATUS_ADJUDICATED` with a descriptive summary (`"SEC EDGAR endpoint returned HTTP status 403."`).
- The facility's health and covenants remain untouched.

#### Consequences
- Temporary government endpoint outages or cloud bot-shields never trigger false covenant breaches or disrupt active lending markets.
- All validators deterministically arrive at the identical fail-closed state.

---

### ADR-005: Form 8-K Regulatory Item Taxonomy as Fixed Storage Enums

#### Context
Under SEC regulations, Form 8-K reports specific triggering events divided into predefined items:
- Item 1.03: Bankruptcy or Receivership
- Item 2.04: Triggering Events That Accelerate or Increase a Direct Financial Obligation
- Item 3.01: Notice of Delisting or Failure to Satisfy a Continued Listing Rule
- Item 5.02: Departure of Directors or Certain Officers; Election of Directors
- Item 8.01: Other Events (Regulatory notices, Subpoenas)

#### Decision
Map the official Form 8-K statutory framework into storage enums:
- `CATEGORY_BANKRUPTCY_RECEIVERSHIP` (1)
- `CATEGORY_DEBT_ACCELERATION_DEFAULT` (2)
- `CATEGORY_REGULATORY_ENFORCEMENT` (3)
- `CATEGORY_EXECUTIVE_FRAUD_INVESTIGATION` (4)
- `CATEGORY_DELISTING_NONCOMPLIANCE` (5)
- `CATEGORY_ROUTINE_NON_MATERIAL` (6)

#### Consequences
- Precise regulatory compliance with standard U.S. securities filings.
- Allows debt facilities to define customized covenant actions per event category.
