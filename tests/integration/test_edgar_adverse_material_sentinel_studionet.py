"""Studionet Integration Tests for EdgarAdverseMaterialSentinel v1.0.0.

Author: 9ytshade
Verifies canonical deployment and live on-chain state on GenLayer Studionet (Chain ID 61999).
Canonical Contract Address: 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f
Deployer Address: 0xb704b624ae5f776b3a3fa7496adcda4db4dcab56
Deployment Tx: 0xe8b67b37474069443065e8fdf2532bfcdb299601d978de1b2501dec7e34d9b41
"""

import json
import re
import subprocess
import urllib.request
import pytest

CANONICAL_ADDRESS = "0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f"
DEPLOYER_ADDRESS = "0xb704b624ae5f776b3a3fa7496adcda4db4dcab56"
RPC_URL = "https://studio.genlayer.com/api"


def rpc_call(method: str, params: list):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GenLayerIntegration/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if "error" in res:
            raise RuntimeError(f"RPC Error: {res['error']}")
        return res.get("result")


def genlayer_call(method: str, *args):
    """Invoke contract view method via genlayer CLI and parse output."""
    cmd = ["genlayer.cmd", "call", CANONICAL_ADDRESS, method]
    if args:
        cmd.extend(["--args"] + [str(a) for a in args])

    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if res.returncode != 0:
        raise RuntimeError(f"genlayer call failed: {res.stderr}\n{res.stdout}")

    match = re.search(r"Result:\s*\n(.*?)(?:\n\n√|\Z)", res.stdout, re.DOTALL)
    if not match:
        raise ValueError(f"Could not parse result from: {res.stdout}")

    raw = match.group(1).strip()
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.isdigit():
        return int(raw)

    if raw.startswith("{") and raw.endswith("}"):
        node_script = "const obj = eval('(' + process.argv[1] + ')'); console.log(JSON.stringify(obj));"
        node_res = subprocess.run(["node", "-e", node_script, raw], capture_output=True, text=True)
        if node_res.returncode == 0:
            return json.loads(node_res.stdout)

    return raw


def test_canonical_contract_schema_on_studionet():
    """Verify that the deployed contract exposes the expected method schema on Studionet."""
    schema = rpc_call("gen_getContractSchema", [CANONICAL_ADDRESS])
    assert schema is not None, "Contract schema must exist"
    methods = schema.get("methods", {})

    expected_methods = [
        "set_governor",
        "register_edgar_domain",
        "toggle_edgar_domain",
        "register_facility",
        "update_facility",
        "reset_covenant_breach",
        "submit_filing_disclosure",
        "adjudicate_filing",
        "get_facility",
        "get_facility_count",
        "is_facility_healthy",
        "is_covenant_breached",
        "should_freeze_tranches",
        "get_issuer_risk_score",
        "get_filing",
        "get_filing_count",
        "get_facility_filings",
        "is_edgar_domain_trusted",
        "get_trusted_edgar_domains",
        "get_governor",
        "validate_equivalence",
    ]
    for m in expected_methods:
        assert m in methods, f"Expected method {m} not found in schema"


def test_governor_matches_deployer():
    """Verify on-chain governor matches deployer address."""
    gov = genlayer_call("get_governor")
    assert isinstance(gov, str)
    assert gov.lower() == DEPLOYER_ADDRESS.lower()


def test_trusted_edgar_domains_initialized():
    """Verify SEC EDGAR domains are trusted out-of-the-box."""
    assert genlayer_call("is_edgar_domain_trusted", "sec.gov") is True
    assert genlayer_call("is_edgar_domain_trusted", "www.sec.gov") is True
    assert genlayer_call("is_edgar_domain_trusted", "data.sec.gov") is True
    assert genlayer_call("is_edgar_domain_trusted", "archives.sec.gov") is True
    assert genlayer_call("is_edgar_domain_trusted", "malicious-hacker.com") is False


def test_registered_facility_telemetry():
    """Verify facility #1 registered in interaction script."""
    fac_count = genlayer_call("get_facility_count")
    assert fac_count >= 1

    fac = genlayer_call("get_facility", 1)
    assert isinstance(fac, dict)
    assert fac["name"] == "Acme Senior Debt Facility"
    assert fac["issuer_cik"] == "0001889922"
    assert fac["issuer_symbol"] == "ACME"
    assert fac["covenant_breach_threshold"] == 70
    assert fac["is_active"] is True
    assert fac["is_covenant_breached"] is False

    assert genlayer_call("is_facility_healthy", 1) is True
    assert genlayer_call("should_freeze_tranches", 1) is False
    assert genlayer_call("get_issuer_risk_score", 1) == 0


def test_adjudicated_filing_telemetry():
    """Verify filing #1 submitted and adjudicated in interaction script."""
    filing_count = genlayer_call("get_filing_count")
    assert filing_count >= 1

    filing = genlayer_call("get_filing", 1)
    assert isinstance(filing, dict)
    assert filing["accession_number"] == "0001889922-24-000001"
    assert filing["facility_id"] == 1
    assert filing["filing_domain"] == "www.sec.gov"
    assert filing["status"] == 1  # STATUS_ADJUDICATED
    assert filing["adjudication_verdict"] == 5  # VERDICT_EDGAR_UNAVAILABLE (fail-closed HTTP 403)
    assert filing["covenant_breach_detected"] is False
