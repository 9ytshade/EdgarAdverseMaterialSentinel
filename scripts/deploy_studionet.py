"""Studionet Deployment & Verification Script for EdgarAdverseMaterialSentinel.

Author: 9ytshade
Deploys the canonical contract to GenLayer Studionet (Chain ID 61999).
"""

import subprocess
import sys
import json
import re

NETWORK_RPC = "https://studio.genlayer.com/api"
CONTRACT_PATH = "contracts/edgar_adverse_material_sentinel.py"


def main():
    print(f"Deploying {CONTRACT_PATH} to GenLayer Studionet ({NETWORK_RPC})...")
    cmd = [
        "genlayer.cmd",
        "deploy",
        "--contract",
        CONTRACT_PATH,
        "--rpc",
        NETWORK_RPC,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print(res.stdout)
    if res.returncode != 0:
        print(f"Deployment failed:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)

    match = re.search(r"Contract deployed at:\s*(0x[a-fA-F0-9]{40})", res.stdout)
    if match:
        addr = match.group(1)
        print(f"Deployment succeeded. Canonical address: {addr}")
        print(f"Explorer URL: https://explorer-studio.genlayer.com/address/{addr}")
    else:
        print("Contract deployed. Check output for address.")


if __name__ == "__main__":
    main()
