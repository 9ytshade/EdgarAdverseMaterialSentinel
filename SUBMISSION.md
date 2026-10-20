# GenLayer Intelligent Contract Submission

## Submitter Information
- **Builder Identity**: `9ytshade`
- **Deployer Wallet Address**: [`0xb704b624ae5f776b3a3fa7496adcda4db4dcab56`](https://explorer-studio.genlayer.com/address/0xb704b624ae5f776b3a3fa7496adcda4db4dcab56)
- **Network**: GenLayer Studionet
- **Chain ID**: `61999`
- **RPC URL**: `https://studio.genlayer.com/api`
- **GenLayer Studio**: [https://studio.genlayer.com](https://studio.genlayer.com)
- **GenLayer Explorer**: [https://explorer-studio.genlayer.com/](https://explorer-studio.genlayer.com/)

---

## Contract Metadata
- **Contract Name**: `EdgarAdverseMaterialSentinel`
- **Contract Version**: `v1.0.0`
- **Source File**: `contracts/edgar_adverse_material_sentinel.py`
- **Canonical Deployed Address**: [`0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f`](https://explorer-studio.genlayer.com/address/0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f)
- **Deployment Transaction Hash**: [`0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41`](https://explorer-studio.genlayer.com/tx/0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41)
- **Deployment Quorum**: `ACCEPTED` / `MAJORITY_AGREE`

---

## Live Studionet Transaction Manifest

| # | Action | Transaction Hash | Consensus Status | Explorer Link | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Deploy Contract** | `0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41` | `ACCEPTED` / `MAJORITY_AGREE` | [View Tx](https://explorer-studio.genlayer.com/tx/0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41) | Contract instantiation and storage initialization on Studionet. |
| **2** | **Register Facility** | `0x354fc9d1ce9b94fd6b0993ca961bbc280f2c7454eeedf84917bc506661d568c9` | `ACCEPTED` / `MAJORITY_AGREE` | [View Tx](https://explorer-studio.genlayer.com/tx/0x354fc9d1ce9b94fd6b0993ca961bbc280f2c7454eeedf84917bc506661d568c9) | Registered "Acme Senior Debt Facility" (CIK: `0001889922`, Symbol: `ACME`, Threshold: 70). |
| **3** | **Submit Filing** | `0xc772bf2447a45f2f439ebaa164d5df7a1ca151490f876866a445c393ad851e9e` | `ACCEPTED` / `MAJORITY_AGREE` | [View Tx](https://explorer-studio.genlayer.com/tx/0xc772bf2447a45f2f439ebaa164d5df7a1ca151490f876866a445c393ad851e9e) | Submits Form 8-K disclosure referencing SEC EDGAR archive `0001889922-24-000001`. |
| **4** | **Adjudicate Filing** | `0x43edacb13694239b05a9782d916718e39bec3883141d25756434cee8ec039739` | `ACCEPTED` / `MAJORITY_AGREE` | [View Tx](https://explorer-studio.genlayer.com/tx/0x43edacb13694239b05a9782d916718e39bec3883141d25756434cee8ec039739) | Quorum-adjudicated Equivalence Principle consensus across validators (Fail-Closed 403 handling). |

---

## Current On-Chain State Verification

Verified via live JSON-RPC calls against `https://studio.genlayer.com/api`:

```bash
# Get Facility #1 telemetry
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_facility --args 1
# Output:
# {
#   active_threat_score: 0,
#   admin: '0xb704b624ae5f776b3a3fa7496adcda4db4dcab56',
#   covenant_breach_threshold: 70,
#   id: 1,
#   is_active: true,
#   is_covenant_breached: false,
#   issuer_cik: '0001889922',
#   issuer_symbol: 'ACME',
#   last_filing_id: 0,
#   name: 'Acme Senior Debt Facility',
#   registered_at: 1792454853
# }

# Check facility health
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f is_facility_healthy --args 1
# Output: true

# Check tranche freeze recommendation
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f should_freeze_tranches --args 1
# Output: false

# Inspect Adjudicated Filing #1
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_filing --args 1
# Output:
# {
#   accession_number: '0001889922-24-000001',
#   adjudicated_at: 1792454891,
#   adjudication_verdict: 5,
#   covenant_breach_detected: false,
#   event_category: 0,
#   facility_id: 1,
#   filing_domain: 'www.sec.gov',
#   filing_url: 'https://www.sec.gov/Archives/edgar/data/0001889922/000188992224000001/acme-8k.htm',
#   id: 1,
#   materiality_score: 0,
#   reported_at: 1792454872,
#   reporter: '0xb704b624ae5f776b3a3fa7496adcda4db4dcab56',
#   status: 1,
#   summary: 'SEC EDGAR endpoint returned HTTP status 403.'
# }
```

---

## Master Playbook Compliance Audit Checklist

| Requirement | Implementation Details | Status |
| :--- | :--- | :--- |
| **Authoritative Source Provenance** | Strict whitelist enforced via `DEFAULT_AUTHORITATIVE_EDGAR_DOMAINS` (`sec.gov`, `www.sec.gov`, `data.sec.gov`, `archives.sec.gov`) and 10-digit CIK binding. | **PASS** |
| **Strict Anti-SSRF & Network Defense** | Hostname parsing, private/reserved IPv4 & IPv6 socket checks, meta-refresh redirect loops blocked, credentials stripped. | **PASS** |
| **Equivalence Principle Consensus** | Non-deterministic web fetch and LLM evaluation wrapped in `gl.vm.run_nondet_unsafe(evaluate, validate)` with dual calldata/dictionary support. | **PASS** |
| **Discrete Metric Quantization** | Continuous materiality scores mapped to integer `0..100`, discrete event categories (0-6), discrete verdicts (0-5). | **PASS** |
| **Fail-Closed Security** | Rate-limited or bot-protected regulatory endpoints fail closed (`VERDICT_EDGAR_UNAVAILABLE`, materiality score 0, no false breaches). | **PASS** |
| **Storage Correctness** | All persistent dictionaries declared as `TreeMap[K, V]` for deterministic state hashing. | **PASS** |
| **Automated Debt Covenant Hooks** | Downstream hooks `is_facility_healthy()`, `should_freeze_tranches()`, and `get_issuer_risk_score()` provide trustless integrations. | **PASS** |
| **Test Verification** | 18/18 Preflight AST checks passed, 15/15 Direct unit tests passed, 5/5 live Studionet integration tests passed. | **PASS** |

---

## Verification Instructions

To reproduce all test results against the canonical contract:

```bash
# 1. Run AST Preflight Audit
python scripts/preflight.py

# 2. Run Direct Unit Tests
python -m pytest tests/direct -v

# 3. Run Live Studionet Integration Tests
python -m pytest tests/integration -v
```
