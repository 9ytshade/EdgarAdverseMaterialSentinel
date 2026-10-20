# Protocol Integration Guide

This guide details how external Real-World Asset (RWA) protocols, tokenized debt pools, private credit funds, cross-chain messaging bridges, and automated keeper bots can integrate `EdgarAdverseMaterialSentinel`.

---

## 1. Solidity Consumer Interface

Smart contracts deploying on EVM or GenLayer compatible environments can consume the Sentinel's state using standard interface definitions:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IEdgarAdverseMaterialSentinel {
    function is_facility_healthy(uint256 facilityId) external view returns (bool);
    function is_covenant_breached(uint256 facilityId) external view returns (bool);
    function should_freeze_tranches(uint256 facilityId) external view returns (bool);
    function get_issuer_risk_score(uint256 facilityId) external view returns (uint8);
    function get_facility(uint256 facilityId) external view returns (
        uint256 id,
        string memory name,
        string memory issuer_cik,
        string memory issuer_symbol,
        uint8 covenant_breach_threshold,
        address admin,
        uint64 registered_at,
        bool is_active,
        bool is_covenant_breached,
        uint8 active_threat_score,
        uint256 last_filing_id
    );
}
```

---

## 2. Example: Autonomous RWA Debt Vault

Below is a complete Solidity implementation of an RWA senior debt vault that halts junior/senior tranche withdrawals and freezes capital deployment if the borrower triggers an SEC Form 8-K covenant breach:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "./IEdgarAdverseMaterialSentinel.sol";

contract ProtectedRWADebtVault is Pausable, Ownable {
    IEdgarAdverseMaterialSentinel public immutable sentinel;
    uint256 public immutable facilityId;

    event TranchesFrozen(uint256 indexed facilityId, uint8 riskScore);
    event FacilityRestored(uint256 indexed facilityId);

    constructor(address _sentinelAddress, uint256 _facilityId) Ownable(msg.sender) {
        sentinel = IEdgarAdverseMaterialSentinel(_sentinelAddress);
        facilityId = _facilityId;
    }

    modifier checkCovenantHealth() {
        if (sentinel.should_freeze_tranches(facilityId)) {
            if (!paused()) {
                _pause();
                emit TranchesFrozen(facilityId, sentinel.get_issuer_risk_score(facilityId));
            }
        }
        _;
    }

    /// @notice Borrowers draw down capital only if covenants are healthy.
    function drawdown(uint256 amount) external whenNotPaused checkCovenantHealth {
        require(sentinel.is_facility_healthy(facilityId), "Covenant breach active");
        // Proceed with capital transfer...
    }

    /// @notice Investors deposit capital only if facility is healthy.
    function deposit(uint256 amount) external whenNotPaused checkCovenantHealth {
        // Accept liquidity...
    }

    /// @notice Administrative emergency unpause once legal waiver is issued.
    function resumeAfterRemediation() external onlyOwner {
        require(!sentinel.is_covenant_breached(facilityId), "Sentinel still reports breach");
        _unpause();
        emit FacilityRestored(facilityId);
    }
}
```

---

## 3. Off-Chain Keeper & Monitoring Integration (Python)

Off-chain automated monitors or keeper bots can watch SEC Form 8-K RSS feeds and trigger on-chain adjudication:

```python
"""Automated SEC EDGAR Monitoring Bot for GenLayer."""

import json
import urllib.request
import subprocess

SENTINEL_ADDRESS = "0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f"
STUDIO_RPC = "https://studio.genlayer.com/api"


def submit_and_adjudicate(facility_id: int, accession_num: str, edgar_url: str):
    print(f"Submitting filing {accession_num} for facility {facility_id}...")

    # 1. Submit Filing
    subprocess.run(
        [
            "genlayer.cmd",
            "write",
            SENTINEL_ADDRESS,
            "submit_filing_disclosure",
            "--rpc",
            STUDIO_RPC,
            "--args",
            str(facility_id),
            accession_num,
            edgar_url,
        ],
        check=True,
    )

    # 2. Get Filing Count to determine filing ID
    res = subprocess.run(
        ["genlayer.cmd", "call", SENTINEL_ADDRESS, "get_filing_count"],
        capture_output=True,
        text=True,
        check=True,
    )
    filing_id = int(res.stdout.strip())

    # 3. Adjudicate Filing
    print(f"Adjudicating filing #{filing_id} across validator quorum...")
    subprocess.run(
        [
            "genlayer.cmd",
            "write",
            SENTINEL_ADDRESS,
            "adjudicate_filing",
            "--rpc",
            STUDIO_RPC,
            "--args",
            str(filing_id),
        ],
        check=True,
    )
    print("Filing successfully adjudicated by multi-validator consensus.")
```

---

## 4. Querying On-Chain State via CLI

```bash
# Check if facility is healthy
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f is_facility_healthy --args 1

# Check if tranches should be frozen
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f should_freeze_tranches --args 1

# Get issuer risk score (0-100)
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_issuer_risk_score --args 1

# Get all filings for facility #1
genlayer call 0xA4823915c16CA686Cc177Fd120F8B3Ee75E3a24f get_facility_filings --args 1
```
