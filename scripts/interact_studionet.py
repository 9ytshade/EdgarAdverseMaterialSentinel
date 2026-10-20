"""Studionet Interaction Script for EdgarAdverseMaterialSentinel.

Author: 9ytshade
Executes live on-chain transactions and view calls against GenLayer Studionet.
"""

import json
import re
import subprocess
import sys

CANONICAL_ADDRESS = "0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f"
RPC_URL = "https://studio.genlayer.com/api"


def run_write(method: str, args_list: list):
    print(f"\n>>> Executing WRITE: {method} with args {args_list}...")
    cmd = [
        "genlayer.cmd",
        "write",
        CANONICAL_ADDRESS,
        method,
        "--rpc",
        RPC_URL,
        "--args",
    ] + [str(a) for a in args_list]

    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if res.returncode != 0:
        print(f"Error in {method}:\n{res.stderr}\n{res.stdout}", file=sys.stderr)
        return False, None
    print(res.stdout)
    match = re.search(r"hash:\s*'(0x[a-fA-F0-9]{64})'", res.stdout)
    tx_hash = match.group(1) if match else None
    return True, tx_hash


def run_call(method: str, args_list: list = None):
    print(f"\n>>> Executing CALL: {method}...")
    cmd = [
        "genlayer.cmd",
        "call",
        CANONICAL_ADDRESS,
        method,
    ]
    if args_list is not None:
        cmd.extend(["--args"] + [str(a) for a in args_list])

    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if res.returncode != 0:
        print(f"Error calling {method}:\n{res.stderr}\n{res.stdout}", file=sys.stderr)
        return None
    print(res.stdout)
    match = re.search(r"Result:\s*\n(.*?)(?:\n\n√|\Z)", res.stdout, re.DOTALL)
    if match:
        return match.group(1).strip()
    return res.stdout


def main():
    print(f"=== Interacting with EdgarAdverseMaterialSentinel at {CANONICAL_ADDRESS} ===")

    admin = "0xb704b624ae5f776b3a3fa7496adcda4db4dcab56"

    # 1. Register Facility
    ok, reg_tx = run_write(
        "register_facility",
        ["Acme Senior Debt Facility", "0001889922", "ACME", 70, admin],
    )
    print(f"register_facility tx: {reg_tx}")

    # 2. Submit Filing Disclosure
    sec_url = "https://www.sec.gov/Archives/edgar/data/0001889922/000188992224000001/acme-8k.htm"
    ok, sub_tx = run_write(
        "submit_filing_disclosure",
        [1, "0001889922-24-000001", sec_url],
    )
    print(f"submit_filing_disclosure tx: {sub_tx}")

    # 3. Adjudicate Filing
    ok, adj_tx = run_write("adjudicate_filing", [1])
    print(f"adjudicate_filing tx: {adj_tx}")

    # 4. View Calls
    run_call("get_facility_count")
    run_call("get_facility", [1])
    run_call("is_facility_healthy", [1])
    run_call("should_freeze_tranches", [1])
    run_call("get_filing", [1])


if __name__ == "__main__":
    main()
