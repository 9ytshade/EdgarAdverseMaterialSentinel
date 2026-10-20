"""Direct Mode Test Suite for EdgarAdverseMaterialSentinel v1.0.0.

Author: 9ytshade
Comprehensive unit and consensus verification using genlayer-test direct mode:
1. Deployment & public storage initialization
2. Authoritative SEC EDGAR provenance enforcement & untrusted domain rejection
3. Network safety, SSRF defenses & structured IP validation
4. Facility registration, ownership & covenant threshold management
5. Multi-validator consensus adjudication:
   - Chapter 11 bankruptcy filing -> covenant breach tripped, tranches frozen
   - Routine earnings update -> facility healthy, tranches safe
   - 404 HTTP failure -> fail-closed EDGAR_UNAVAILABLE
   - Malformed LLM response -> fail-closed EDGAR_UNAVAILABLE
6. Downstream consumer views: is_facility_healthy, is_covenant_breached, should_freeze_tranches
"""

from pathlib import Path
import pytest

CONTRACT_PATH = str(
    Path(__file__).resolve().parent.parent.parent
    / "contracts"
    / "edgar_adverse_material_sentinel.py"
)
FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"

DEFAULT_8K_HTML = (FIXTURES_DIR / "sample_8k_default.html").read_text(encoding="utf-8")
ROUTINE_8K_HTML = (FIXTURES_DIR / "sample_8k_routine.html").read_text(encoding="utf-8")


def deploy_contract(direct_deploy):
    return direct_deploy(CONTRACT_PATH)


def test_deployment_initialization(direct_deploy, direct_vm):
    contract = deploy_contract(direct_deploy)
    governor = contract.get_governor()
    assert governor == direct_vm.sender

    domains = contract.get_trusted_edgar_domains()
    assert "sec.gov" in domains
    assert "data.sec.gov" in domains
    assert contract.is_edgar_domain_trusted("sec.gov") is True
    assert contract.is_edgar_domain_trusted("untrusted-blog.xyz") is False
    assert contract.get_facility_count() == 0
    assert contract.get_filing_count() == 0


def test_governance_controls(direct_deploy, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    # Non-governor cannot register domain
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only governor can register EDGAR domains"):
        contract.register_edgar_domain("filings.sec.gov")

    # Governor can register domain
    direct_vm.sender = direct_alice
    contract.register_edgar_domain("filings.sec.gov")
    assert contract.is_edgar_domain_trusted("filings.sec.gov") is True

    # Governor can toggle domain
    contract.toggle_edgar_domain("filings.sec.gov", False)
    assert contract.is_edgar_domain_trusted("filings.sec.gov") is False

    # Transfer governance
    contract.set_governor(direct_bob)
    assert contract.get_governor() == direct_bob


def test_facility_registration_and_lifecycle(direct_deploy, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Senior Debt Pool",
        issuer_cik="1889922",  # Auto-padded to 0001889922
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    assert fac_id == 1
    assert contract.get_facility_count() == 1

    fac = contract.get_facility(1)
    assert fac["issuer_cik"] == "0001889922"
    assert fac["issuer_symbol"] == "ACME"
    assert fac["is_covenant_breached"] is False
    assert contract.is_facility_healthy(1) is True
    assert contract.should_freeze_tranches(1) is False

    # Non-admin cannot update facility
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only facility admin or governor can update facility"):
        contract.update_facility(1, 80, True)

    # Admin can update facility
    direct_vm.sender = direct_alice
    contract.update_facility(1, 80, True)
    assert contract.get_facility(1)["covenant_breach_threshold"] == 80


def test_edgar_provenance_enclosure(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Senior Debt Pool",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )

    valid_accession = "0001193125-24-001234"

    # Untrusted domain rejected
    with direct_vm.expect_revert("not in authoritative EDGAR whitelist"):
        contract.submit_filing_disclosure(
            facility_id=fac_id,
            accession_number=valid_accession,
            filing_url="https://fake-edgar-sec.com/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
        )

    # CIK mismatch in URL path rejected
    with direct_vm.expect_revert("does not contain registered issuer CIK"):
        contract.submit_filing_disclosure(
            facility_id=fac_id,
            accession_number=valid_accession,
            filing_url="https://www.sec.gov/Archives/edgar/data/0000999999/000119312524001234/acme-8k.htm",
        )

    # Invalid accession number format rejected
    with direct_vm.expect_revert("Accession number must match SEC format"):
        contract.submit_filing_disclosure(
            facility_id=fac_id,
            accession_number="invalid-acc-123",
            filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
        )

    # Valid submission succeeds
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=valid_accession,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )
    assert filing_id == 1
    filing = contract.get_filing(1)
    assert filing["status"] == 0  # STATUS_PENDING


def test_ssrf_and_ip_validation_rules(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Senior Debt Pool",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"

    # Insecure scheme
    with direct_vm.expect_revert("Scheme 'ftp' not allowed"):
        contract.submit_filing_disclosure(
            fac_id, acc, "ftp://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/8k.htm"
        )

    # Credentials in URL
    with direct_vm.expect_revert("Credentials in URL are forbidden"):
        contract.submit_filing_disclosure(
            fac_id, acc, "https://admin:pass@www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/8k.htm"
        )

    # Non-standard port
    with direct_vm.expect_revert("Non-standard port"):
        contract.submit_filing_disclosure(
            fac_id, acc, "https://www.sec.gov:8080/Archives/edgar/data/0001889922/000119312524001234/8k.htm"
        )


def test_adjudicate_chapter_11_triggers_covenant_breach(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    # Mock web fetch
    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 200,
            "body": DEFAULT_8K_HTML,
        },
    )

    # Mock LLM evaluation
    direct_vm.mock_llm(
        r"decentralized securities analyst verifying an SEC Form 8-K",
        (
            '{"is_target_issuer_confirmed": true, "event_category": 1, "materiality_score": 95, '
            '"covenant_breach": true, "verdict": 1, '
            '"summary": "Acme filed voluntary Chapter 11 bankruptcy; senior debt accelerated."}'
        ),
    )

    contract.adjudicate_filing(filing_id)

    # Check filing state
    filing = contract.get_filing(filing_id)
    assert filing["status"] == 1  # STATUS_ADJUDICATED
    assert filing["event_category"] == 1  # CATEGORY_BANKRUPTCY_RECEIVERSHIP
    assert filing["materiality_score"] == 95
    assert filing["covenant_breach_detected"] is True
    assert filing["adjudication_verdict"] == 1  # VERDICT_MATERIAL_ADVERSE_CONFIRMED

    # Check facility state: Covenant Breach TRIPPED!
    fac = contract.get_facility(fac_id)
    assert fac["is_covenant_breached"] is True
    assert fac["active_threat_score"] == 95

    # Downstream consumer checks
    assert contract.is_facility_healthy(fac_id) is False
    assert contract.is_covenant_breached(fac_id) is True
    assert contract.should_freeze_tranches(fac_id) is True
    assert contract.get_issuer_risk_score(fac_id) == 95

    # Reset covenant breach by admin
    contract.reset_covenant_breach(fac_id)
    fac_after = contract.get_facility(fac_id)
    assert fac_after["is_covenant_breached"] is False
    assert fac_after["active_threat_score"] == 0
    assert contract.is_facility_healthy(fac_id) is True
    assert contract.should_freeze_tranches(fac_id) is False


def test_adjudicate_routine_8k_keeps_facility_healthy(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 200,
            "body": ROUTINE_8K_HTML,
        },
    )

    direct_vm.mock_llm(
        r"decentralized securities analyst verifying an SEC Form 8-K",
        (
            '{"is_target_issuer_confirmed": true, "event_category": 6, "materiality_score": 15, '
            '"covenant_breach": false, "verdict": 2, '
            '"summary": "Routine Q3 earnings update with no adverse financial impact."}'
        ),
    )

    contract.adjudicate_filing(filing_id)

    filing = contract.get_filing(filing_id)
    assert filing["adjudication_verdict"] == 2  # VERDICT_ROUTINE_NON_MATERIAL
    assert filing["covenant_breach_detected"] is False

    # Facility remains healthy
    assert contract.is_facility_healthy(fac_id) is True
    assert contract.is_covenant_breached(fac_id) is False
    assert contract.should_freeze_tranches(fac_id) is False


def test_fail_closed_on_404_not_found(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 404,
            "body": "Not Found",
        },
    )

    contract.adjudicate_filing(filing_id)

    filing = contract.get_filing(filing_id)
    assert filing["adjudication_verdict"] == 5  # VERDICT_EDGAR_UNAVAILABLE
    assert filing["materiality_score"] == 0
    assert filing["covenant_breach_detected"] is False

    # Facility covenant MUST NOT trip on unreachable 404
    assert contract.is_facility_healthy(fac_id) is True
    assert contract.should_freeze_tranches(fac_id) is False


def test_fail_closed_on_malformed_llm_json(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 200,
            "body": DEFAULT_8K_HTML,
        },
    )

    direct_vm.mock_llm(
        r"decentralized securities analyst verifying an SEC Form 8-K",
        "NOT VALID JSON OUTPUT",
    )

    contract.adjudicate_filing(filing_id)

    filing = contract.get_filing(filing_id)
    assert filing["adjudication_verdict"] == 5  # VERDICT_EDGAR_UNAVAILABLE
    assert filing["covenant_breach_detected"] is False


def test_unauthorized_covenant_reset_rejected(direct_deploy, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only facility admin or governor can reset covenant breach"):
        contract.reset_covenant_breach(fac_id)


def test_cannot_submit_filing_to_inactive_facility(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )

    contract.update_facility(fac_id, 70, False)

    acc = "0001193125-24-001234"
    with direct_vm.expect_revert("is inactive"):
        contract.submit_filing_disclosure(
            facility_id=fac_id,
            accession_number=acc,
            filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
        )


def test_cannot_adjudicate_already_adjudicated_filing(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 200,
            "body": ROUTINE_8K_HTML,
        },
    )

    direct_vm.mock_llm(
        r"decentralized securities analyst verifying an SEC Form 8-K",
        (
            '{"is_target_issuer_confirmed": true, "event_category": 6, "materiality_score": 15, '
            '"covenant_breach": false, "verdict": 2, '
            '"summary": "Routine announcement."}'
        ),
    )

    contract.adjudicate_filing(filing_id)

    with direct_vm.expect_revert("is already adjudicated"):
        contract.adjudicate_filing(filing_id)


def test_meta_refresh_redirect_to_untrusted_domain_fails_closed(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )
    acc = "0001193125-24-001234"
    filing_id = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number=acc,
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524001234/acme-8k.htm",
    )

    evil_meta = '<html><head><meta http-equiv="refresh" content="0; url=https://evil-attacker.com/fake-8k.html"></head><body>Redirecting...</body></html>'
    direct_vm.mock_web(
        r"sec\.gov/.*",
        {
            "status": 200,
            "body": evil_meta,
        },
    )

    contract.adjudicate_filing(filing_id)

    filing = contract.get_filing(filing_id)
    assert filing["adjudication_verdict"] == 5  # VERDICT_EDGAR_UNAVAILABLE
    assert filing["covenant_breach_detected"] is False


def test_facility_filings_listing(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    fac_id = contract.register_facility(
        facility_name="Acme Corporate Holdings",
        issuer_cik="0001889922",
        issuer_symbol="ACME",
        covenant_breach_threshold=70,
        admin_address=direct_alice,
    )

    f1 = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number="0001193125-24-000001",
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524000001/doc1.htm",
    )
    f2 = contract.submit_filing_disclosure(
        facility_id=fac_id,
        accession_number="0001193125-24-000002",
        filing_url="https://www.sec.gov/Archives/edgar/data/0001889922/000119312524000002/doc2.htm",
    )

    assert contract.get_facility_filings(fac_id) == [1, 2]


def test_validate_equivalence_view(direct_deploy, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    contract = deploy_contract(direct_deploy)

    leader_agree = {
        "verdict": 1,
        "covenant_breach": True,
        "event_category": 1,
        "materiality_score": 90,
    }
    local_agree = {
        "verdict": 1,
        "covenant_breach": True,
        "event_category": 1,
        "materiality_score": 85,  # Delta 5 <= 15
    }
    assert contract.validate_equivalence(leader_agree, local_agree) is True

    local_diverge = {
        "verdict": 1,
        "covenant_breach": True,
        "event_category": 1,
        "materiality_score": 60,  # Delta 30 > 15
    }
    assert contract.validate_equivalence(leader_agree, local_diverge) is False
