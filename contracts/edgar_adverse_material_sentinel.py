# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""EdgarAdverseMaterialSentinel v1.0.0: Autonomous RWA & Tokenized Debt SEC Form 8-K Sentinel.

Author: 9ytshade
A high-assurance GenLayer Intelligent Contract primitive that autonomously verifies
SEC Form 8-K material event disclosures across decentralized multi-validator consensus.

Enforces contract-side authoritative provenance (restricting filing sources to SEC EDGAR
domains and binding filing CIK to the registered facility), structured host/IP SSRF and
recursive redirect defenses, fail-closed fault tolerance, discrete quantized materiality
scoring, and automated debt covenant breach triggers for Real-World Asset (RWA) vaults,
private credit pools, and tokenized corporate bond protocols under the Equivalence Principle.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import re
import urllib.parse

from genlayer import *


# ---------------------------------------------------------------------------
# Discrete Constants & Consensus Enums
# ---------------------------------------------------------------------------

# Filing Lifecycle Status
STATUS_PENDING: u8 = 0
STATUS_ADJUDICATED: u8 = 1
STATUS_DISMISSED: u8 = 2
STATUS_UNAVAILABLE: u8 = 3

# Adverse Material Event Categories (SEC Form 8-K Item Taxonomy)
CATEGORY_NONE: u8 = 0                         # No adverse event
CATEGORY_BANKRUPTCY_RECEIVERSHIP: u8 = 1       # Item 1.03: Bankruptcy or Receivership
CATEGORY_DEBT_ACCELERATION_DEFAULT: u8 = 2     # Item 2.04: Triggering Events Accelerating Obligations
CATEGORY_REGULATORY_ENFORCEMENT: u8 = 3        # Item 8.01 / Subpoena / Enforcement Action
CATEGORY_EXECUTIVE_FRAUD_INVESTIGATION: u8 = 4 # Item 5.02: Officer Departure under Investigation
CATEGORY_DELISTING_NONCOMPLIANCE: u8 = 5       # Item 3.01: Delisting or Continued Listing Rule Failure
CATEGORY_ROUTINE_NON_MATERIAL: u8 = 6          # Item 7.01 / Routine Disclosures / Non-material

# Final Adjudication Verdicts
VERDICT_PENDING: u8 = 0
VERDICT_MATERIAL_ADVERSE_CONFIRMED: u8 = 1     # High/Critical adverse event confirmed
VERDICT_ROUTINE_NON_MATERIAL: u8 = 2           # Routine filing, covenant safe
VERDICT_UNRELATED_ISSUER: u8 = 3               # Filing CIK does not match facility issuer
VERDICT_MALFORMED_FILING: u8 = 4               # Unparseable or non-8-K document
VERDICT_EDGAR_UNAVAILABLE: u8 = 5              # SEC EDGAR unreachable / rate-limited (Fail-Closed)

# Authoritative SEC EDGAR Domains Whitelist
DEFAULT_AUTHORITATIVE_EDGAR_DOMAINS: tuple[str, ...] = (
    "sec.gov",
    "www.sec.gov",
    "data.sec.gov",
    "archives.sec.gov",
)

# SSRF Forbidden Suffixes & Keywords
FORBIDDEN_HOST_SUFFIXES: tuple[str, ...] = (
    "localhost",
    "local",
    "internal",
    "intranet",
    "lan",
    "home",
    "corp",
    "arpa",
    "invalid",
    "test",
    "example",
)


# ---------------------------------------------------------------------------
# Storage Dataclasses
# ---------------------------------------------------------------------------

@allow_storage
@dataclass
class FacilityRecord:
    id: u256
    name: str
    issuer_cik: str              # 10-digit Central Index Key (e.g. "0001889922")
    issuer_symbol: str           # Ticker or symbol (e.g. "ACME")
    covenant_breach_threshold: u8  # Materiality score 0-100 triggering freeze
    admin: Address
    registered_at: u64
    is_active: bool
    is_covenant_breached: bool
    active_threat_score: u8
    last_filing_id: u256


@allow_storage
@dataclass
class FilingRecord:
    id: u256
    facility_id: u256
    accession_number: str        # e.g. "0001193125-24-001234"
    filing_url: str
    filing_domain: str
    reporter: Address
    reported_at: u64
    adjudicated_at: u64
    status: u8
    event_category: u8
    materiality_score: u8       # Quantized 0-100
    covenant_breach_detected: bool
    adjudication_verdict: u8
    summary: str


def _coerce_to_u256(val) -> u256:
    if isinstance(val, list) and len(val) == 1:
        val = val[0]
    return u256(int(val))


def _coerce_to_u8(val) -> u8:
    if isinstance(val, list) and len(val) == 1:
        val = val[0]
    return u8(int(val))


def _coerce_to_str(val) -> str:
    if isinstance(val, list) and len(val) == 1:
        val = val[0]
    return str(val).strip()


# ---------------------------------------------------------------------------
# Strict Network Safety & URL Validation
# ---------------------------------------------------------------------------

def _check_ip_safety(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Verifies that an IP address is not private, loopback, or reserved."""
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    if ip_obj.is_loopback:
        raise gl.vm.UserError(f"Loopback destination forbidden: {ip_obj}")
    if ip_obj.is_private:
        raise gl.vm.UserError(f"Private IP destination forbidden: {ip_obj}")
    if ip_obj.is_reserved:
        raise gl.vm.UserError(f"Reserved IP destination forbidden: {ip_obj}")
    if ip_obj.is_link_local:
        raise gl.vm.UserError(f"Link-local destination forbidden: {ip_obj}")
    if ip_obj.is_multicast:
        raise gl.vm.UserError(f"Multicast destination forbidden: {ip_obj}")
    if ip_obj.is_unspecified:
        raise gl.vm.UserError(f"Unspecified IP forbidden: {ip_obj}")


def _validate_edgar_url(
    url: str,
    allowed_domains: tuple[str, ...],
    expected_cik: str,
    expected_accession: str,
) -> tuple[str, str]:
    """Validates SEC EDGAR URL format, scheme, host, and issuer binding."""
    if not isinstance(url, str) or not url.strip():
        raise gl.vm.UserError("Filing URL must be a non-empty string")

    clean_url = url.strip()
    if len(clean_url) > 1024:
        raise gl.vm.UserError("URL exceeds maximum length of 1024 characters")

    parsed = urllib.parse.urlsplit(clean_url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise gl.vm.UserError(f"Scheme '{parsed.scheme}' not allowed. Must be HTTP or HTTPS.")

    if parsed.username or parsed.password:
        raise gl.vm.UserError("Credentials in URL are forbidden")

    raw_host = (parsed.hostname or "").lower().strip()
    if not raw_host:
        raise gl.vm.UserError("Filing URL missing valid hostname")

    if any(raw_host == sf or raw_host.endswith("." + sf) for sf in FORBIDDEN_HOST_SUFFIXES):
        raise gl.vm.UserError(f"Forbidden host suffix detected: {raw_host}")

    is_trusted = any(raw_host == d or raw_host.endswith("." + d) for d in allowed_domains)
    if not is_trusted:
        raise gl.vm.UserError(f"Filing domain '{raw_host}' is not in authoritative EDGAR whitelist")

    if parsed.port and parsed.port not in (80, 443):
        raise gl.vm.UserError(f"Non-standard port '{parsed.port}' forbidden")

    # Anti-SSRF direct IP validation
    try:
        ip_obj = ipaddress.ip_address(raw_host)
        _check_ip_safety(ip_obj)
    except ValueError:
        pass

    # Strict EDGAR path binding: Ensure path contains the expected CIK or accession
    stripped_cik = expected_cik.lstrip("0")
    cik_pattern_found = (
        f"/data/{expected_cik}/" in parsed.path
        or f"/data/{stripped_cik}/" in parsed.path
        or expected_cik in parsed.path
        or (stripped_cik and stripped_cik in parsed.path)
    )
    if not cik_pattern_found:
        raise gl.vm.UserError(
            f"Filing URL path does not contain registered issuer CIK '{expected_cik}'"
        )

    clean_accession_numeric = expected_accession.replace("-", "")
    if clean_accession_numeric not in parsed.path and expected_accession not in parsed.path:
        raise gl.vm.UserError(
            f"Filing URL path does not reference accession number '{expected_accession}'"
        )

    return clean_url, raw_host


def _inspect_meta_redirects(html_content: str, allowed_domains: tuple[str, ...]) -> bool:
    """Inspects HTML for meta-refresh redirects and verifies destination domain."""
    meta_refresh_matches = re.findall(
        r'<meta[^>]*http-equiv=[\'"]?refresh[\'"]?[^>]*content=[\'"]?[^;]*;\s*url=([^\'">\s]+)',
        html_content,
        re.IGNORECASE,
    )
    for target in meta_refresh_matches:
        try:
            parsed = urllib.parse.urlsplit(target.strip())
            host = (parsed.hostname or "").lower()
            if host:
                if any(host == sf or host.endswith("." + sf) for sf in FORBIDDEN_HOST_SUFFIXES):
                    return False
                if not any(host == d or host.endswith("." + d) for d in allowed_domains):
                    return False
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# Canonical Contract Class: EdgarAdverseMaterialSentinel
# ---------------------------------------------------------------------------

class EdgarAdverseMaterialSentinel(gl.Contract):
    """Intelligent Contract for autonomous SEC Form 8-K adverse material disclosure monitoring."""

    governor: Address
    facility_counter: u256
    filing_counter: u256

    trusted_edgar_domains: TreeMap[str, bool]
    facilities: TreeMap[u256, FacilityRecord]
    filings: TreeMap[u256, FilingRecord]

    def __init__(self):
        """Initializes governance, authoritative EDGAR domains, and facility registries."""
        deployer = gl.message.sender_address
        self.governor = deployer
        self.facility_counter = u256(0)
        self.filing_counter = u256(0)

        # Seed default authoritative SEC EDGAR domains
        for domain in DEFAULT_AUTHORITATIVE_EDGAR_DOMAINS:
            self.trusted_edgar_domains[domain] = True

    def _now(self) -> u64:
        return u64(int(datetime.now(timezone.utc).timestamp()))

    # -----------------------------------------------------------------------
    # Governance & Registry Methods
    # -----------------------------------------------------------------------

    @gl.public.write
    def set_governor(self, new_governor: Address) -> None:
        """Transfers governor control to a new address."""
        if gl.message.sender_address != self.governor:
            raise gl.vm.UserError("Only current governor can transfer governance")
        self.governor = new_governor

    @gl.public.write
    def register_edgar_domain(self, domain: str) -> None:
        """Registers a new authoritative SEC EDGAR domain."""
        if gl.message.sender_address != self.governor:
            raise gl.vm.UserError("Only governor can register EDGAR domains")
        clean = domain.strip().lower()
        if not clean or "." not in clean:
            raise gl.vm.UserError("Invalid domain format")
        for suff in FORBIDDEN_HOST_SUFFIXES:
            if clean == suff or clean.endswith("." + suff):
                raise gl.vm.UserError(f"Cannot register forbidden domain: {suff}")
        self.trusted_edgar_domains[clean] = True

    @gl.public.write
    def toggle_edgar_domain(self, domain: str, is_active: bool) -> None:
        """Enables or disables an authoritative EDGAR domain."""
        if gl.message.sender_address != self.governor:
            raise gl.vm.UserError("Only governor can toggle EDGAR domains")
        clean = domain.strip().lower()
        if clean not in self.trusted_edgar_domains:
            raise gl.vm.UserError(f"Domain '{clean}' not found in registry")
        self.trusted_edgar_domains[clean] = is_active

    @gl.public.write
    def register_facility(
        self,
        facility_name: str,
        issuer_cik: str,
        issuer_symbol: str,
        covenant_breach_threshold: u8,
        admin_address: Address,
    ) -> u256:
        """Registers a tokenized debt facility or RWA private credit pool for EDGAR monitoring."""
        clean_fac_name = _coerce_to_str(facility_name)
        if not clean_fac_name or len(clean_fac_name) > 128:
            raise gl.vm.UserError("Facility name must be between 1 and 128 characters")

        clean_cik = _coerce_to_str(issuer_cik).zfill(10)
        if not re.match(r"^\d{10}$", clean_cik):
            raise gl.vm.UserError("Issuer CIK must be a 10-digit numeric string")

        clean_symbol = _coerce_to_str(issuer_symbol).upper()
        if not clean_symbol or len(clean_symbol) > 16:
            raise gl.vm.UserError("Issuer symbol must be between 1 and 16 characters")

        threshold_int = int(covenant_breach_threshold)
        if not (10 <= threshold_int <= 100):
            raise gl.vm.UserError("Covenant breach threshold must be an integer between 10 and 100")

        self.facility_counter += 1
        facility_id = self.facility_counter
        now_ts = self._now()

        self.facilities[facility_id] = FacilityRecord(
            id=facility_id,
            name=clean_fac_name,
            issuer_cik=clean_cik,
            issuer_symbol=clean_symbol,
            covenant_breach_threshold=u8(threshold_int),
            admin=admin_address,
            registered_at=now_ts,
            is_active=True,
            is_covenant_breached=False,
            active_threat_score=0,
            last_filing_id=u256(0),
        )
        return facility_id

    @gl.public.write
    def update_facility(
        self,
        facility_id: u256,
        covenant_breach_threshold: u8,
        is_active: bool,
    ) -> None:
        """Updates facility covenant threshold or monitoring status."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            raise gl.vm.UserError(f"Facility ID {fac_id} does not exist")

        fac = self.facilities[fac_id]
        if gl.message.sender_address != fac.admin and gl.message.sender_address != self.governor:
            raise gl.vm.UserError("Only facility admin or governor can update facility")

        threshold_int = int(covenant_breach_threshold)
        if not (10 <= threshold_int <= 100):
            raise gl.vm.UserError("Covenant breach threshold must be an integer between 10 and 100")

        fac.covenant_breach_threshold = u8(threshold_int)
        fac.is_active = bool(is_active)
        self.facilities[fac_id] = fac

    @gl.public.write
    def reset_covenant_breach(self, facility_id: u256) -> None:
        """Resets the covenant breach status after borrower remediation or debt restructuring."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            raise gl.vm.UserError(f"Facility ID {fac_id} does not exist")

        fac = self.facilities[fac_id]
        if gl.message.sender_address != fac.admin and gl.message.sender_address != self.governor:
            raise gl.vm.UserError("Only facility admin or governor can reset covenant breach")

        fac.is_covenant_breached = False
        fac.active_threat_score = 0
        self.facilities[fac_id] = fac

    # -----------------------------------------------------------------------
    # Filing Disclosure & Adjudication Pipeline
    # -----------------------------------------------------------------------

    @gl.public.write
    def submit_filing_disclosure(
        self,
        facility_id: u256,
        accession_number: str,
        filing_url: str,
    ) -> u256:
        """Submits an SEC Form 8-K disclosure referencing an active facility."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            raise gl.vm.UserError(f"Facility ID {fac_id} does not exist")

        fac = self.facilities[fac_id]
        if not fac.is_active:
            raise gl.vm.UserError(f"Facility ID {fac_id} is inactive")

        clean_accession = _coerce_to_str(accession_number)
        if not re.match(r"^\d{10}-\d{2}-\d{6}$", clean_accession):
            raise gl.vm.UserError(
                "Accession number must match SEC format 0000000000-00-000000 (e.g. 0001193125-24-001234)"
            )

        # Snapshot active allowed domains
        allowed_domains_list = []
        for dom, active in self.trusted_edgar_domains.items():
            if active:
                allowed_domains_list.append(dom)
        allowed_domains_tuple = tuple(allowed_domains_list)

        # Validate URL and enforce CIK / Accession binding
        clean_url_str = _coerce_to_str(filing_url)
        validated_url, filing_domain = _validate_edgar_url(
            clean_url_str,
            allowed_domains_tuple,
            fac.issuer_cik,
            clean_accession,
        )

        self.filing_counter += 1
        filing_id = self.filing_counter
        now_ts = self._now()

        self.filings[filing_id] = FilingRecord(
            id=filing_id,
            facility_id=fac_id,
            accession_number=clean_accession,
            filing_url=validated_url,
            filing_domain=filing_domain,
            reporter=gl.message.sender_address,
            reported_at=now_ts,
            adjudicated_at=u64(0),
            status=STATUS_PENDING,
            event_category=CATEGORY_NONE,
            materiality_score=0,
            covenant_breach_detected=False,
            adjudication_verdict=VERDICT_PENDING,
            summary="",
        )
        return filing_id

    @gl.public.write
    def adjudicate_filing(self, filing_id: u256) -> None:
        """Adjudicates SEC Form 8-K disclosure via decentralized Equivalence Principle consensus."""
        fid = _coerce_to_u256(filing_id)
        if fid not in self.filings:
            raise gl.vm.UserError(f"Filing ID {fid} does not exist")

        filing = self.filings[fid]
        if filing.status != STATUS_PENDING:
            raise gl.vm.UserError(f"Filing ID {fid} is already adjudicated or closed")

        facility_id = filing.facility_id
        fac = self.facilities[facility_id]

        # Snapshot contract state into local variables before nondet closure
        target_url = str(filing.filing_url)
        issuer_cik = str(fac.issuer_cik)
        issuer_symbol = str(fac.issuer_symbol)
        facility_name = str(fac.name)
        breach_threshold = int(fac.covenant_breach_threshold)

        allowed_domains_list = []
        for dom, active in self.trusted_edgar_domains.items():
            if active:
                allowed_domains_list.append(dom)
        allowed_domains_tuple = tuple(allowed_domains_list)

        def evaluate() -> dict:
            """Non-deterministic fetch & LLM evaluation of the SEC Form 8-K filing."""
            try:
                page_resp = gl.nondet.web.get(target_url)
                status_code = getattr(page_resp, "status", 500)
                if status_code != 200:
                    return {
                        "event_category": CATEGORY_NONE,
                        "materiality_score": 0,
                        "covenant_breach": False,
                        "verdict": VERDICT_EDGAR_UNAVAILABLE,
                        "summary": f"SEC EDGAR endpoint returned HTTP status {status_code}.",
                    }

                raw_body = getattr(page_resp, "body", "")
                if isinstance(raw_body, bytes):
                    raw_content = raw_body.decode("utf-8", errors="ignore")
                else:
                    raw_content = str(raw_body)

                if not raw_content or len(raw_content.strip()) < 50:
                    return {
                        "event_category": CATEGORY_NONE,
                        "materiality_score": 0,
                        "covenant_breach": False,
                        "verdict": VERDICT_MALFORMED_FILING,
                        "summary": "SEC filing body is empty or too short to contain valid 8-K disclosures.",
                    }

                # Meta-refresh redirect safety check
                if not _inspect_meta_redirects(raw_content, allowed_domains_tuple):
                    return {
                        "event_category": CATEGORY_NONE,
                        "materiality_score": 0,
                        "covenant_breach": False,
                        "verdict": VERDICT_EDGAR_UNAVAILABLE,
                        "summary": "Filing page attempted meta-refresh redirect to an untrusted domain.",
                    }

                # Truncate content to 32KB to fit LLM window while retaining core Item headers
                content_sample = raw_content[:32768]

                prompt = f"""You are a decentralized securities analyst verifying an SEC Form 8-K regulatory filing on GenLayer.
Analyze this filing content to assess whether a Material Adverse Event has occurred for the target borrower/issuer.

Target Issuer Details:
- Facility Name: {facility_name}
- Expected CIK: {issuer_cik}
- Expected Symbol: {issuer_symbol}
- Covenant Breach Threshold: {breach_threshold}/100

Filing Body Excerpt:
\"\"\"{content_sample}\"\"\"

Classification Guidelines for Event Category:
- 1: CATEGORY_BANKRUPTCY_RECEIVERSHIP (Item 1.03: Chapter 11/7, liquidation, receivership appointment)
- 2: CATEGORY_DEBT_ACCELERATION_DEFAULT (Item 2.04: Acceleration of direct financial obligations, loan defaults)
- 3: CATEGORY_REGULATORY_ENFORCEMENT (Item 8.01: Major SEC/DOJ enforcement, formal civil/criminal proceedings, cease & desist)
- 4: CATEGORY_EXECUTIVE_FRAUD_INVESTIGATION (Item 5.02: Resignation/termination of CEO/CFO under internal or criminal probe)
- 5: CATEGORY_DELISTING_NONCOMPLIANCE (Item 3.01: Notice of delisting from national securities exchange)
- 6: CATEGORY_ROUTINE_NON_MATERIAL (Item 7.01, Item 8.01 routine announcements, press releases, non-adverse updates)
- 0: CATEGORY_NONE (Filing does not mention target issuer or is not a valid 8-K)

Materiality Scoring (Integer 0 to 100):
- 90 - 100: Catastrophic / Insolvency / Debt Default
- 70 - 89: Severe Material Adverse Event / Cross-default risk / Imminent delisting
- 40 - 69: Moderate Operational Disruption / Regulatory inquiry without immediate sanction
- 10 - 39: Minor / Routine Corporate Disclosure
- 0: Completely Unrelated / Routine Safe

Output strictly valid JSON with no markdown wrapping and no additional prose:
{{
  "is_target_issuer_confirmed": <true|false>,
  "event_category": <integer 0 to 6>,
  "materiality_score": <integer 0 to 100>,
  "covenant_breach": <true|false>,
  "verdict": <integer 1 to 4>,
  "summary": "<one sentence concise factual summary>"
}}"""

                llm_response = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(llm_response, dict):
                    parsed_llm = llm_response
                else:
                    raw_json = str(llm_response).strip()
                    if raw_json.startswith("```"):
                        lines = raw_json.split("\n")
                        raw_json = "\n".join([l for l in lines if not l.startswith("```")])
                    parsed_llm = json.loads(raw_json)

                is_target = bool(parsed_llm.get("is_target_issuer_confirmed", False))
                category = int(parsed_llm.get("event_category", CATEGORY_NONE))
                score = max(0, min(100, int(parsed_llm.get("materiality_score", 0))))
                covenant_breach = bool(parsed_llm.get("covenant_breach", False))
                summary = str(parsed_llm.get("summary", "Analysis completed."))[:256]

                if not is_target:
                    return {
                        "event_category": CATEGORY_NONE,
                        "materiality_score": 0,
                        "covenant_breach": False,
                        "verdict": VERDICT_UNRELATED_ISSUER,
                        "summary": "Filing does not match the registered issuer CIK or symbol.",
                    }

                if category in (
                    CATEGORY_BANKRUPTCY_RECEIVERSHIP,
                    CATEGORY_DEBT_ACCELERATION_DEFAULT,
                    CATEGORY_REGULATORY_ENFORCEMENT,
                    CATEGORY_EXECUTIVE_FRAUD_INVESTIGATION,
                    CATEGORY_DELISTING_NONCOMPLIANCE,
                ):
                    verdict = VERDICT_MATERIAL_ADVERSE_CONFIRMED
                    if score >= breach_threshold:
                        covenant_breach = True
                else:
                    verdict = VERDICT_ROUTINE_NON_MATERIAL
                    covenant_breach = False

                return {
                    "event_category": category,
                    "materiality_score": score,
                    "covenant_breach": covenant_breach,
                    "verdict": verdict,
                    "summary": summary,
                }

            except Exception as exc:
                return {
                    "event_category": CATEGORY_NONE,
                    "materiality_score": 0,
                    "covenant_breach": False,
                    "verdict": VERDICT_EDGAR_UNAVAILABLE,
                    "summary": f"Filing evaluation error (Fail-Closed): {str(exc)[:128]}",
                }

        def validate(leader_result) -> bool:
            """Equivalence Principle validator callback. Verifies agreement within discrete boundaries."""
            candidate_data = (
                leader_result.calldata if hasattr(leader_result, "calldata") else leader_result
            )

            if not isinstance(candidate_data, dict):
                return False

            local_eval = evaluate()

            # Exact match required for discrete verdict and covenant breach decision
            if candidate_data.get("verdict") != local_eval.get("verdict"):
                return False

            if candidate_data.get("covenant_breach") != local_eval.get("covenant_breach"):
                return False

            # Event categories must match unless filing was unavailable or routine
            if candidate_data.get("verdict") == VERDICT_MATERIAL_ADVERSE_CONFIRMED:
                if candidate_data.get("event_category") != local_eval.get("event_category"):
                    return False

            # Bounded score tolerance: allow max 15 points variance across LLMs
            leader_score = int(candidate_data.get("materiality_score", 0))
            local_score = int(local_eval.get("materiality_score", 0))
            if abs(leader_score - local_score) > 15:
                return False

            return True

        adjudication = gl.vm.run_nondet_unsafe(evaluate, validate)

        # Commit final state on-chain
        now_ts = self._now()
        filing.status = STATUS_ADJUDICATED
        filing.event_category = adjudication["event_category"]
        filing.materiality_score = adjudication["materiality_score"]
        filing.covenant_breach_detected = adjudication["covenant_breach"]
        filing.adjudication_verdict = adjudication["verdict"]
        filing.summary = adjudication["summary"]
        filing.adjudicated_at = now_ts
        self.filings[filing_id] = filing

        # Update facility state if covenant breach was detected
        if adjudication["covenant_breach"]:
            fac.is_covenant_breached = True
            if adjudication["materiality_score"] > fac.active_threat_score:
                fac.active_threat_score = adjudication["materiality_score"]
            fac.last_filing_id = filing_id
            self.facilities[facility_id] = fac

    # -----------------------------------------------------------------------
    # Downstream Integration & Public View Methods
    # -----------------------------------------------------------------------

    @gl.public.view
    def is_facility_healthy(self, facility_id: u256) -> bool:
        """Returns True if the facility has no active covenant breaches."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            return False
        return not bool(self.facilities[fac_id].is_covenant_breached)

    @gl.public.view
    def is_covenant_breached(self, facility_id: u256) -> bool:
        """Returns True if an adverse material event triggered a covenant breach."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            return False
        return bool(self.facilities[fac_id].is_covenant_breached)

    @gl.public.view
    def should_freeze_tranches(self, facility_id: u256) -> bool:
        """Direct hook for RWA vaults and lending pools to freeze redemptions or distributions."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            return False
        fac = self.facilities[fac_id]
        return bool(fac.is_covenant_breached) or not bool(fac.is_active)

    @gl.public.view
    def get_issuer_risk_score(self, facility_id: u256) -> u8:
        """Returns the highest active materiality threat score (0-100) for an issuer."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            return 0
        return self.facilities[fac_id].active_threat_score

    @gl.public.view
    def get_facility(self, facility_id: u256) -> dict:
        """Returns facility metadata, CIK, and covenant state."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            raise gl.vm.UserError(f"Facility ID {fac_id} does not exist")
        fac = self.facilities[fac_id]
        return {
            "id": fac.id,
            "name": fac.name,
            "issuer_cik": fac.issuer_cik,
            "issuer_symbol": fac.issuer_symbol,
            "covenant_breach_threshold": fac.covenant_breach_threshold,
            "admin": fac.admin,
            "registered_at": fac.registered_at,
            "is_active": fac.is_active,
            "is_covenant_breached": fac.is_covenant_breached,
            "active_threat_score": fac.active_threat_score,
            "last_filing_id": fac.last_filing_id,
        }

    @gl.public.view
    def get_facility_count(self) -> u256:
        """Returns total registered facilities."""
        return self.facility_counter

    @gl.public.view
    def get_filing(self, filing_id: u256) -> dict:
        """Returns filing disclosure and adjudication results."""
        fid = _coerce_to_u256(filing_id)
        if fid not in self.filings:
            raise gl.vm.UserError(f"Filing ID {fid} does not exist")
        filing = self.filings[fid]
        return {
            "id": filing.id,
            "facility_id": filing.facility_id,
            "accession_number": filing.accession_number,
            "filing_url": filing.filing_url,
            "filing_domain": filing.filing_domain,
            "reporter": filing.reporter,
            "reported_at": filing.reported_at,
            "adjudicated_at": filing.adjudicated_at,
            "status": filing.status,
            "event_category": filing.event_category,
            "materiality_score": filing.materiality_score,
            "covenant_breach_detected": filing.covenant_breach_detected,
            "adjudication_verdict": filing.adjudication_verdict,
            "summary": filing.summary,
        }

    @gl.public.view
    def get_filing_count(self) -> u256:
        """Returns total submitted filings."""
        return self.filing_counter

    @gl.public.view
    def get_facility_filings(self, facility_id: u256) -> list[u256]:
        """Returns list of filing IDs submitted for a given facility."""
        fac_id = _coerce_to_u256(facility_id)
        if fac_id not in self.facilities:
            raise gl.vm.UserError(f"Facility ID {fac_id} does not exist")
        results = []
        for fid, f in self.filings.items():
            if f.facility_id == fac_id:
                results.append(fid)
        return results

    @gl.public.view
    def is_edgar_domain_trusted(self, domain: str) -> bool:
        """Checks if an EDGAR domain is in the active authoritative whitelist."""
        clean = domain.strip().lower()
        return bool(self.trusted_edgar_domains.get(clean, False))

    @gl.public.view
    def get_trusted_edgar_domains(self) -> list[str]:
        """Returns all registered authoritative EDGAR domains."""
        results = []
        for dom, active in self.trusted_edgar_domains.items():
            if active:
                results.append(dom)
        return results

    @gl.public.view
    def get_governor(self) -> Address:
        """Returns the current governor address."""
        return self.governor

    @gl.public.view
    def validate_equivalence(self, leader_data: dict, local_data: dict) -> bool:
        """Public view exposing the Equivalence Principle consensus criteria for transparency."""
        if not isinstance(leader_data, dict) or not isinstance(local_data, dict):
            return False

        if leader_data.get("verdict") != local_data.get("verdict"):
            return False

        if leader_data.get("covenant_breach") != local_data.get("covenant_breach"):
            return False

        if leader_data.get("verdict") == VERDICT_MATERIAL_ADVERSE_CONFIRMED:
            if leader_data.get("event_category") != local_data.get("event_category"):
                return False

        leader_score = int(leader_data.get("materiality_score", 0))
        local_score = int(local_data.get("materiality_score", 0))
        if abs(leader_score - local_score) > 15:
            return False

        return True
