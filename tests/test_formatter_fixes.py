"""
Mocked regression tests for the Batch-2 formatter fixes (pure unit tests).

- format_bill_summary / format_bills_list must not crash when the API returns
  `latestAction: null` (the get_bills 'NoneType' object has no attribute 'get').
- format_bill_detail must tolerate null dict-valued fields (cosponsors, etc.).
- format_bill_subjects must handle the live dict shape
  {legislativeSubjects:[...], policyArea:{...}} (the get_bill_subjects
  'str' object has no attribute 'get'), and a legacy list.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from congress_api.features.buckets.bills.formatters import BillsFormatter


def test_bill_summary_tolerates_null_latest_action():
    bill = {"type": "HR", "number": "6", "congress": 119,
            "title": "Reserved", "latestAction": None, "url": "u"}
    out = BillsFormatter.format_bill_summary(bill)
    assert "Error formatting" not in out
    assert "HR 6" in out


def test_bills_list_tolerates_null_latest_action():
    resp = {"bills": [
        {"type": "HR", "number": "6", "congress": 119, "latestAction": None, "url": "u"},
        {"type": "HR", "number": "9", "congress": 119,
         "latestAction": {"text": "Referred", "actionDate": "2025-01-03"}, "url": "u2"},
    ]}
    out = BillsFormatter.format_bills_list(resp, "Bills")
    assert "Error formatting" not in out
    assert "HR 6" in out and "HR 9" in out
    assert "Referred" in out


def test_bill_detail_tolerates_null_dict_fields():
    bill = {"type": "HR", "number": "1", "congress": 119, "title": "Test",
            "cosponsors": None, "committees": None, "policyArea": None,
            "subjects": None, "latestAction": None, "textVersions": None}
    out = BillsFormatter.format_bill_detail(bill)
    assert "Error formatting" not in out
    assert "HR 1" in out


def test_bill_subjects_handles_live_dict_shape():
    subjects = {
        "legislativeSubjects": [{"name": "Abortion"}, {"name": "Accounting and auditing"}],
        "policyArea": {"name": "Economics and Public Finance"},
    }
    out = BillsFormatter.format_bill_subjects(subjects)
    assert "Error formatting" not in out
    assert "Policy Area:** Economics and Public Finance" in out
    assert "- Abortion" in out


def test_bill_subjects_handles_legacy_list():
    out = BillsFormatter.format_bill_subjects([{"name": "Taxation"}])
    assert "Error formatting" not in out
    assert "- Taxation" in out


def test_bill_subjects_empty():
    assert BillsFormatter.format_bill_subjects({}) == "No subjects found."
    assert BillsFormatter.format_bill_subjects([]) == "No subjects found."
