"""
HLR lookup providers.

A provider takes a normalised 10-digit Indian number and returns a
``LookupResult``. Two providers ship here:

  * ``MockProvider``  – offline, deterministic, needs no network or API key.
    Great for developing the app and demoing the bulk pipeline. Every result
    is clearly marked ``source="mock"`` so it is never mistaken for real data.

  * ``HttpProvider``  – calls a real third-party HLR API over HTTPS. Real HLR
    lookups need SS7 access, which you buy from a gateway. This class targets
    the common JSON shape used by providers such as hlr-lookups.com / Telnyx /
    generic gateways, and the field mapping is configurable via env vars so you
    can point it at whichever service you use without editing code.

Select the active provider with the ``HLR_PROVIDER`` env var ("mock" or "http").
"""

import os
import time
import hashlib
from dataclasses import dataclass, asdict, field
from typing import Optional

try:
    import requests
except ImportError:  # requests is only needed for the real HTTP provider
    requests = None


# Canonical connectivity statuses we normalise every provider onto.
STATUS_CONNECTED = "CONNECTED"       # reachable / active
STATUS_ABSENT = "ABSENT"             # valid but currently unreachable (off / no coverage)
STATUS_INVALID = "INVALID"           # not a valid subscriber number
STATUS_UNKNOWN = "UNKNOWN"           # lookup could not determine status
STATUS_ERROR = "ERROR"               # lookup failed (network / auth / quota)


@dataclass
class LookupResult:
    msisdn: str                       # 10-digit national number
    e164: str = ""                    # +91XXXXXXXXXX
    status: str = STATUS_UNKNOWN      # one of STATUS_*
    valid: bool = False               # is it a live/valid subscriber number
    reachable: Optional[bool] = None  # currently reachable (None if unknown)
    current_operator: str = ""        # network the number is on now
    original_operator: str = ""       # network it was originally allocated to
    is_ported: Optional[bool] = None  # ported via MNP (None if unknown)
    roaming: Optional[bool] = None    # roaming outside home network
    mccmnc: str = ""                  # mobile country/network code
    country: str = "IN"
    imsi: str = ""                    # usually masked/absent on cheaper plans
    source: str = ""                  # which provider produced this
    error: str = ""                   # populated when status == ERROR
    checked_at: float = field(default_factory=time.time)

    def as_dict(self):
        return asdict(self)


class BaseProvider:
    name = "base"

    def lookup(self, msisdn: str) -> LookupResult:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
#  Offline mock provider
# ─────────────────────────────────────────────────────────────────────────────
class MockProvider(BaseProvider):
    """
    Deterministic, offline lookups. The same number always yields the same
    result (hash-seeded) so demos and tests are reproducible. No number is ever
    actually contacted; this is purely synthetic data for pipeline testing.
    """

    name = "mock"
    _OPERATORS = ["Jio", "Airtel", "Vi (Vodafone Idea)", "BSNL"]
    _MCCMNC = {
        "Jio": "405857",
        "Airtel": "40410",
        "Vi (Vodafone Idea)": "40411",
        "BSNL": "40471",
    }

    def __init__(self, latency: float = 0.0):
        self._latency = latency

    def _seed(self, msisdn: str) -> int:
        h = hashlib.sha256(msisdn.encode("utf-8")).digest()
        return int.from_bytes(h[:8], "big")

    def lookup(self, msisdn: str) -> LookupResult:
        from .india import to_e164, guess_operator

        if self._latency:
            time.sleep(self._latency)

        seed = self._seed(msisdn)
        # ~90% valid, of those ~85% currently reachable.
        valid = (seed % 10) != 0
        reachable = valid and (((seed >> 4) % 100) < 85)
        ported = valid and (((seed >> 8) % 100) < 30)  # ~30% ported

        original = guess_original(seed, self._OPERATORS)
        current = original
        if ported:
            current = self._OPERATORS[(seed >> 12) % len(self._OPERATORS)]

        if not valid:
            status = STATUS_INVALID
        elif reachable:
            status = STATUS_CONNECTED
        else:
            status = STATUS_ABSENT

        return LookupResult(
            msisdn=msisdn,
            e164=to_e164(msisdn),
            status=status,
            valid=valid,
            reachable=reachable if valid else False,
            current_operator=current if valid else "",
            original_operator=original if valid else "",
            is_ported=ported if valid else None,
            roaming=bool((seed >> 16) % 20 == 0) if valid else None,  # ~5% roaming
            mccmnc=self._MCCMNC.get(current, "") if valid else "",
            country="IN",
            source=self.name,
        )


def guess_original(seed: int, operators):
    return operators[seed % len(operators)]


# ─────────────────────────────────────────────────────────────────────────────
#  Real HTTP provider
# ─────────────────────────────────────────────────────────────────────────────
class HttpProvider(BaseProvider):
    """
    Generic REST HLR provider.

    Configure via environment variables (sensible defaults target an
    hlr-lookups.com-style JSON endpoint; adjust to your gateway):

      HLR_API_URL         Full endpoint URL. The MSISDN is sent as a query
                          param named by HLR_API_MSISDN_PARAM (default: "msisdn").
      HLR_API_KEY         API key/token.
      HLR_API_KEY_HEADER  Header to send the key in (default: "Authorization").
                          Set to "" to instead pass the key as a query param
                          named by HLR_API_KEY_PARAM.
      HLR_API_KEY_PARAM   Query-param name for the key (default: "api_key").
      HLR_API_KEY_PREFIX  Prefix for the header value (default: "Bearer ").
      HLR_API_E164        "1" to send +91E164 instead of the 10-digit number.
      HLR_API_TIMEOUT     Per-request timeout seconds (default: 20).

    Response field mapping (dot-path into the JSON, override to fit your API):
      HLR_MAP_STATUS      default: "hlr.status"        (e.g. CONNECTED/ABSENT)
      HLR_MAP_CURRENT_OP  default: "hlr.currentNetworkName"
      HLR_MAP_ORIGINAL_OP default: "hlr.originalNetworkName"
      HLR_MAP_PORTED      default: "hlr.isPorted"
      HLR_MAP_ROAMING     default: "hlr.isRoaming"
      HLR_MAP_MCCMNC      default: "hlr.mccmnc"
      HLR_MAP_IMSI        default: "hlr.imsi"
    """

    name = "http"

    # Provider status strings that mean "reachable / live".
    _CONNECTED_WORDS = {"connected", "active", "reachable", "delivered", "ok", "valid"}
    _ABSENT_WORDS = {"absent", "unreachable", "off", "switched_off", "not_reachable"}
    _INVALID_WORDS = {"invalid", "not_valid", "unknown_subscriber", "unallocated"}

    def __init__(self):
        if requests is None:
            raise RuntimeError("The 'requests' package is required for HttpProvider.")
        self.url = os.environ.get("HLR_API_URL", "").strip()
        self.key = os.environ.get("HLR_API_KEY", "").strip()
        self.msisdn_param = os.environ.get("HLR_API_MSISDN_PARAM", "msisdn")
        self.key_header = os.environ.get("HLR_API_KEY_HEADER", "Authorization")
        self.key_param = os.environ.get("HLR_API_KEY_PARAM", "api_key")
        self.key_prefix = os.environ.get("HLR_API_KEY_PREFIX", "Bearer ")
        self.send_e164 = os.environ.get("HLR_API_E164", "0") == "1"
        self.timeout = float(os.environ.get("HLR_API_TIMEOUT", "20"))
        self.map = {
            "status": os.environ.get("HLR_MAP_STATUS", "hlr.status"),
            "current_op": os.environ.get("HLR_MAP_CURRENT_OP", "hlr.currentNetworkName"),
            "original_op": os.environ.get("HLR_MAP_ORIGINAL_OP", "hlr.originalNetworkName"),
            "ported": os.environ.get("HLR_MAP_PORTED", "hlr.isPorted"),
            "roaming": os.environ.get("HLR_MAP_ROAMING", "hlr.isRoaming"),
            "mccmnc": os.environ.get("HLR_MAP_MCCMNC", "hlr.mccmnc"),
            "imsi": os.environ.get("HLR_MAP_IMSI", "hlr.imsi"),
        }
        if not self.url:
            raise RuntimeError(
                "HLR_API_URL is not set. Set the real-provider env vars or use "
                "HLR_PROVIDER=mock for offline testing."
            )

    @staticmethod
    def _dig(obj, dotpath):
        cur = obj
        for part in dotpath.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def _classify(self, status_raw):
        s = str(status_raw or "").strip().lower()
        if s in self._CONNECTED_WORDS:
            return STATUS_CONNECTED, True
        if s in self._ABSENT_WORDS:
            return STATUS_ABSENT, False
        if s in self._INVALID_WORDS:
            return STATUS_INVALID, False
        return STATUS_UNKNOWN, None

    @staticmethod
    def _as_bool(v):
        if isinstance(v, bool):
            return v
        if v is None:
            return None
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "y"):
            return True
        if s in ("0", "false", "no", "n"):
            return False
        return None

    def lookup(self, msisdn: str) -> LookupResult:
        from .india import to_e164

        e164 = to_e164(msisdn)
        result = LookupResult(msisdn=msisdn, e164=e164, source=self.name, country="IN")

        params = {self.msisdn_param: e164 if self.send_e164 else msisdn}
        headers = {"Accept": "application/json"}
        if self.key:
            if self.key_header:
                headers[self.key_header] = f"{self.key_prefix}{self.key}"
            else:
                params[self.key_param] = self.key

        try:
            resp = requests.get(self.url, params=params, headers=headers,
                                timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network / auth / quota / bad JSON
            result.status = STATUS_ERROR
            result.error = f"{type(exc).__name__}: {exc}"
            return result

        status_raw = self._dig(data, self.map["status"])
        status, reachable = self._classify(status_raw)
        result.status = status
        result.reachable = reachable
        result.valid = status in (STATUS_CONNECTED, STATUS_ABSENT)
        result.current_operator = self._dig(data, self.map["current_op"]) or ""
        result.original_operator = self._dig(data, self.map["original_op"]) or ""
        result.is_ported = self._as_bool(self._dig(data, self.map["ported"]))
        result.roaming = self._as_bool(self._dig(data, self.map["roaming"]))
        result.mccmnc = str(self._dig(data, self.map["mccmnc"]) or "")
        result.imsi = str(self._dig(data, self.map["imsi"]) or "")
        return result


def get_provider() -> BaseProvider:
    """Return the provider selected by the HLR_PROVIDER env var (default mock)."""
    choice = os.environ.get("HLR_PROVIDER", "mock").strip().lower()
    if choice == "http":
        return HttpProvider()
    # Optional artificial latency for the mock, to simulate network in demos.
    latency = float(os.environ.get("HLR_MOCK_LATENCY", "0") or "0")
    return MockProvider(latency=latency)
