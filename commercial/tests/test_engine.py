from commercial.engine import decide, money, validate_policy
import pytest

def test_safe_default():
    receipt = {'receipt_id': 'T1', 'date': '2026-11-10', 'vendor': 'Supply', 'technician': 'Alex', 'job_number': 'J1', 'card_last4': '1234', 'total': '10.00', 'lines': [{'description':'gloves','amount':'9.00','tax':'1.00'}]}
    assert decide(receipt, {})['verdict'] == 'needs_review'

def test_invalid_numbers():
    for amount in ['NaN', 'Infinity', '-1', '1.234']:
        with pytest.raises(ValueError):
            money(amount)

def test_policy_rejects_new_rules():
    with pytest.raises(ValueError):
        validate_policy({'auto_approve_unknown': True})
