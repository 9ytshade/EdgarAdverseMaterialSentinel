# Deployment & Verification Guide

This guide describes how `EdgarAdverseMaterialSentinel` was deployed to GenLayer Studionet and how any developer, auditor, or validator can reproduce and verify the deployment.

---

## 1. Network & Environment Configuration

| Setting | Value |
| :--- | :--- |
| **Network Name** | GenLayer Studionet |
| **RPC Endpoint** | `https://studio.genlayer.com/api` |
| **GenLayer Studio** | [https://studio.genlayer.com](https://studio.genlayer.com) |
| **GenLayer Explorer** | [https://explorer-studio.genlayer.com/](https://explorer-studio.genlayer.com/) |
| **Chain ID** | `61999` |
| **Deployer Address** | [`0xb704b624ae5f776b3a3fa7496adcda4db4dcab56`](https://explorer-studio.genlayer.com/address/0xb704b624ae5f776b3a3fa7496adcda4db4dcab56) |
| **Canonical Contract Address** | [`0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f`](https://explorer-studio.genlayer.com/address/0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f) |

---

## 2. Prerequisites & Installation

Ensure Python 3.11+ is installed along with the GenLayer CLI and testing framework:

```bash
# Clone repository
git clone https://github.com/9ytshade/EdgarAdverseMaterialSentinel.git
cd EdgarAdverseMaterialSentinel

# Install Python requirements
pip install -r requirements.txt
pip install -r requirements-test.txt
```

---

## 3. Automated Preflight Checks

Before deploying to Studionet, the codebase must pass all 18 AST preflight compliance checks:

```bash
python scripts/preflight.py
```

Expected output:
```
============================================================
ALL 18/18 PREFLIGHT CHECKS PASSED PERFECTLY.
Contract conforms 100% with Master Playbook (v1.1) standards.
============================================================
```

---

## 4. Deployment Walkthrough

The contract was deployed via `scripts/deploy_studionet.py`:

```bash
python scripts/deploy_studionet.py
```

### Studionet Consensus Output:
```json
{
  "Transaction Hash": "0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41",
  "Contract Address": "0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f",
  "Status": "ACCEPTED",
  "Result": "MAJORITY_AGREE"
}
```

---

## 5. Live On-Chain Interactions

The deployed contract was initialized and tested with live transactions via `scripts/interact_studionet.py`:

```bash
python scripts/interact_studionet.py
```

### Transaction Manifest:
1. **Register Facility**:
   - Method: `register_facility("Acme Senior Debt Facility", "0001889922", "ACME", 70, "0xb704b624ae5f776b3a3fa7496adcda4db4dcab56")`
   - Tx Hash: [`0x354fc9d1ce9b94fd6b0993ca961bbc280f2c7454eeedf84917bc506661d568c9`](https://explorer-studio.genlayer.com/tx/0x354fc9d1ce9b94fd6b0993ca961bbc280f2c7454eeedf84917bc506661d568c9)
   - Status: `ACCEPTED` / `MAJORITY_AGREE`

2. **Submit Filing Disclosure**:
   - Method: `submit_filing_disclosure(1, "0001889922-24-000001", "https://www.sec.gov/Archives/edgar/data/0001889922/000188992224000001/acme-8k.htm")`
   - Tx Hash: [`0xc772bf2447a45f2f439ebaa164d5df7a1ca151490f876866a445c393ad851e9e`](https://explorer-studio.genlayer.com/tx/0xc772bf2447a45f2f439ebaa164d5df7a1ca151490f876866a445c393ad851e9e)
   - Status: `ACCEPTED` / `MAJORITY_AGREE`

3. **Adjudicate Filing**:
   - Method: `adjudicate_filing(1)`
   - Tx Hash: [`0x43edacb13694239b05a9782d916718e39bec3883141d25756434cee8ec039739`](https://explorer-studio.genlayer.com/tx/0x43edacb13694239b05a9782d916718e39bec3883141d25756434cee8ec039739)
   - Status: `ACCEPTED` / `MAJORITY_AGREE`

---

## 6. On-Chain Verification Commands

Query the contract directly using the GenLayer CLI:

```bash
# Verify facility count
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_facility_count

# Check facility health
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f is_facility_healthy --args 1

# Inspect filing adjudication
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_filing --args 1

# Check trusted EDGAR domains
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f is_edgar_domain_trusted --args "sec.gov"
```
