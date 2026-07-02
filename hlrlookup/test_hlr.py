"""
Unit tests for the HLR lookup core. Run with:  python -m pytest -q
(or plain `python test_hlr.py` for a no-dependency smoke run).
"""

from hlr.india import normalize_msisdn, validate_indian_mobile, to_e164
from hlr.providers import MockProvider, STATUS_CONNECTED, STATUS_ABSENT, STATUS_INVALID
from hlr.engine import BulkJob


def test_normalize_formats():
    for raw in ["9876543210", "+91 98765 43210", "09876543210",
                "919876543210", "0091-9876543210", "+919876543210"]:
        assert normalize_msisdn(raw) == "9876543210", raw


def test_reject_invalid():
    for bad in ["1234567890", "5876543210", "98765", "", "abcd",
                "12345678901234", None]:
        assert normalize_msisdn(bad) is None, bad
        assert validate_indian_mobile(bad) is False


def test_e164():
    assert to_e164("9876543210") == "+919876543210"


def test_mock_is_deterministic():
    p = MockProvider()
    a = p.lookup("9876543210")
    b = p.lookup("9876543210")
    assert a.status == b.status
    assert a.current_operator == b.current_operator
    assert a.status in (STATUS_CONNECTED, STATUS_ABSENT, STATUS_INVALID)


def test_bulk_dedup_and_invalid():
    raw = ["9876543210", "9876543210", "+91 98765 43210",  # 3× same number
           "1234567890", "notanumber", "9123456780"]
    job = BulkJob(raw, concurrency=4, rate_per_sec=0)
    assert job.total == 2                    # two unique valid numbers
    assert job.duplicates == 2               # two extra copies of the first
    assert len(job.invalid) == 2             # two junk inputs
    job.run()
    assert job.status == "done"
    assert len(job.results) == 2
    assert job.completed == 2
    csv = job.to_csv()
    assert "msisdn" in csv.splitlines()[0]


def test_bulk_1000():
    nums = []
    for i in range(1000):
        nums.append("6789"[i % 4] + str(100000000 + (i * 998237) % 899999999)[:9])
    job = BulkJob(nums, concurrency=20, rate_per_sec=0)
    job.run()
    assert job.status == "done"
    assert job.completed == job.total
    s = job.summary()
    assert sum(s["by_status"].values()) == len(job.results)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\nAll {len(fns)} tests passed.")
