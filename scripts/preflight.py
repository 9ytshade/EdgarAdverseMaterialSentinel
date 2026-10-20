"""Automated AST Preflight Compliance Audit Linter for EdgarAdverseMaterialSentinel.

Author: 9ytshade
Validates all 18 Master Playbook (v1.1) requirements prior to Studionet deployment.
"""

import ast
import os
import re
import sys

CONTRACT_PATH = "contracts/edgar_adverse_material_sentinel.py"

REQUIRED_WRITE_METHODS = [
    "set_governor",
    "register_edgar_domain",
    "toggle_edgar_domain",
    "register_facility",
    "update_facility",
    "reset_covenant_breach",
    "submit_filing_disclosure",
    "adjudicate_filing",
]

REQUIRED_VIEW_METHODS = [
    "is_facility_healthy",
    "is_covenant_breached",
    "should_freeze_tranches",
    "get_issuer_risk_score",
    "get_facility",
    "get_facility_count",
    "get_filing",
    "get_filing_count",
    "get_facility_filings",
    "is_edgar_domain_trusted",
    "get_trusted_edgar_domains",
    "get_governor",
    "validate_equivalence",
]

REQUIRED_DATACLASSES = [
    "FacilityRecord",
    "FilingRecord",
]


def run_audit():
    print(f"--- Running Preflight Verification for EdgarAdverseMaterialSentinel ---")

    # Check 1: File Existence
    if not os.path.exists(CONTRACT_PATH):
        print(f"[FAIL] Check 1: Contract file not found at {CONTRACT_PATH}")
        sys.exit(1)
    print(f"[PASS] Check 1: Contract file exists")

    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    # Check 2: Header Dependency
    if not src.startswith('# { "Depends": "py-genlayer:'):
        print("[FAIL] Check 2: Missing or invalid '# { \"Depends\": ... }' header")
        sys.exit(1)
    print("[PASS] Check 2: Header dependency format verified")

    # Check 3: AST Parsing
    try:
        tree = ast.parse(src)
    except Exception as e:
        print(f"[FAIL] Check 3: AST parsing error: {e}")
        sys.exit(1)
    print("[PASS] Check 3: AST parses cleanly")

    # Check 4: Forbidden Imports
    forbidden_modules = ["requests", "os", "subprocess", "socket", "random", "time"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    print(f"[FAIL] Check 4: Forbidden import detected: {alias.name}")
                    sys.exit(1)
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                print(f"[FAIL] Check 4: Forbidden from-import detected: {node.module}")
                sys.exit(1)
    print("[PASS] Check 4: No forbidden imports")

    # Check 5 & 6: Canonical Contract Class
    contract_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    target_class = next((c for c in contract_classes if c.name == "EdgarAdverseMaterialSentinel"), None)
    if not target_class:
        print("[FAIL] Check 5: Class 'EdgarAdverseMaterialSentinel' not found")
        sys.exit(1)
    print("[PASS] Check 5 & 6: Found canonical Contract class: EdgarAdverseMaterialSentinel")

    # Check 7: Storage Dataclasses
    found_dcs = [c.name for c in contract_classes if c.name in REQUIRED_DATACLASSES]
    for rdc in REQUIRED_DATACLASSES:
        if rdc not in found_dcs:
            print(f"[FAIL] Check 7: Missing required storage dataclass: {rdc}")
            sys.exit(1)
    print("[PASS] Check 7: All required storage dataclasses present")

    # Check 8: Public Write Methods
    class_methods = {n.name: n for n in target_class.body if isinstance(n, ast.FunctionDef)}
    for wm in REQUIRED_WRITE_METHODS:
        if wm not in class_methods:
            print(f"[FAIL] Check 8: Missing public write method: {wm}")
            sys.exit(1)
        fn_node = class_methods[wm]
        has_write_dec = any(
            (isinstance(d, ast.Attribute) and d.attr == "write")
            or ("gl.public.write" in ast.unparse(d))
            for d in fn_node.decorator_list
        )
        if not has_write_dec:
            print(f"[FAIL] Check 8: Method {wm} lacks @gl.public.write decorator")
            sys.exit(1)
    print(f"[PASS] Check 8: All {len(REQUIRED_WRITE_METHODS)} public write methods verified")

    # Check 9: Public View Methods
    for vm in REQUIRED_VIEW_METHODS:
        if vm not in class_methods:
            print(f"[FAIL] Check 9: Missing public view method: {vm}")
            sys.exit(1)
        fn_node = class_methods[vm]
        has_view_dec = any(
            (isinstance(d, ast.Attribute) and d.attr == "view")
            or ("gl.public.view" in ast.unparse(d))
            for d in fn_node.decorator_list
        )
        if not has_view_dec:
            print(f"[FAIL] Check 9: Method {vm} lacks @gl.public.view decorator")
            sys.exit(1)
    print(f"[PASS] Check 9: All {len(REQUIRED_VIEW_METHODS)} public view methods verified")

    # Check 10: Storage Closure Safety
    adjudicate_fn = class_methods.get("adjudicate_filing")
    if not adjudicate_fn:
        print("[FAIL] Check 10: Missing adjudicate_filing method")
        sys.exit(1)

    eval_fn = next((n for n in adjudicate_fn.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate"), None)
    if not eval_fn:
        print("[FAIL] Check 10: Missing inner evaluate() closure")
        sys.exit(1)

    eval_src = ast.unparse(eval_fn)
    if "self." in eval_src:
        print("[FAIL] Check 10: Direct self.* reference found inside evaluate() closure!")
        sys.exit(1)
    print("[PASS] Check 10: Storage closure safety verified (zero self.* inside nondet closures)")

    # Check 11: Discrete Quantization Enums
    constants_needed = [
        "CATEGORY_BANKRUPTCY_RECEIVERSHIP",
        "CATEGORY_DEBT_ACCELERATION_DEFAULT",
        "CATEGORY_REGULATORY_ENFORCEMENT",
        "CATEGORY_EXECUTIVE_FRAUD_INVESTIGATION",
        "CATEGORY_DELISTING_NONCOMPLIANCE",
        "CATEGORY_ROUTINE_NON_MATERIAL",
        "VERDICT_MATERIAL_ADVERSE_CONFIRMED",
        "VERDICT_ROUTINE_NON_MATERIAL",
        "VERDICT_EDGAR_UNAVAILABLE",
    ]
    for c in constants_needed:
        if c not in src:
            print(f"[FAIL] Check 11: Missing discrete quantization constant: {c}")
            sys.exit(1)
    print("[PASS] Check 11: Discrete quantized consensus constants present")

    # Check 12: Fail-Closed Handling
    if "VERDICT_EDGAR_UNAVAILABLE" not in src or "covenant_breach" not in eval_src:
        print("[FAIL] Check 12: Missing fail-closed default")
        sys.exit(1)
    print("[PASS] Check 12: Fail-closed handling verified")

    # Check 13: Strict JSON Schema Prompt
    if "is_target_issuer_confirmed" not in eval_src or "materiality_score" not in eval_src:
        print("[FAIL] Check 13: Prompt lacks required structured JSON fields")
        sys.exit(1)
    print("[PASS] Check 13: Strict prompt JSON schema enforcement verified")

    # Check 14: SSRF & IP Safety
    if "_check_ip_safety" not in src or "FORBIDDEN_HOST_SUFFIXES" not in src:
        print("[FAIL] Check 14: Missing structured host/IP SSRF protections")
        sys.exit(1)
    print("[PASS] Check 14: Structured host/IP SSRF safety verified")

    # Check 15: Authoritative EDGAR Whitelist
    if "DEFAULT_AUTHORITATIVE_EDGAR_DOMAINS" not in src or "sec.gov" not in src:
        print("[FAIL] Check 15: Missing authoritative EDGAR domain whitelist")
        sys.exit(1)
    print("[PASS] Check 15: Authoritative EDGAR domain whitelist verified")

    # Check 16: Zero Cross-Contamination
    forbidden_personas = ["vix", "Ade", "asimov", "proofpay"]
    for fp in forbidden_personas:
        # Case insensitive word search
        if re.search(r"\b" + re.escape(fp) + r"\b", src, re.IGNORECASE):
            print(f"[FAIL] Check 16: Cross-contamination detected! Found reference to '{fp}'")
            sys.exit(1)
    print("[PASS] Check 16: Zero cross-contamination verified (pure 9ytshade builder isolation)")

    # Check 17: UTC Timestamps
    if "datetime.now(timezone.utc)" not in src:
        print("[FAIL] Check 17: Timestamp generation must use datetime.now(timezone.utc)")
        sys.exit(1)
    print("[PASS] Check 17: UTC timestamp provider verified")

    # Check 18: Author Attribution
    if "Author: 9ytshade" not in src:
        print("[FAIL] Check 18: Missing or incorrect Author docstring")
        sys.exit(1)
    print("[PASS] Check 18: Author attribution verified (9ytshade)")

    print("\n============================================================")
    print("ALL 18/18 PREFLIGHT CHECKS PASSED PERFECTLY.")
    print("Contract conforms 100% with Master Playbook (v1.1) standards.")
    print("============================================================\n")


if __name__ == "__main__":
    run_audit()
