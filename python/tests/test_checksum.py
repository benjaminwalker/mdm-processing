from datetime import date

from mdm_processing.core.checksum import compute_checksum


def test_same_attributes_same_checksum():
    a = compute_checksum({"email": "a@example.com", "name": "Alice"})
    b = compute_checksum({"email": "a@example.com", "name": "Alice"})

    assert a == b


def test_key_order_does_not_affect_checksum():
    a = compute_checksum({"email": "a@example.com", "name": "Alice"})
    b = compute_checksum({"name": "Alice", "email": "a@example.com"})

    assert a == b


def test_different_values_produce_different_checksum():
    a = compute_checksum({"email": "a@example.com"})
    b = compute_checksum({"email": "b@example.com"})

    assert a != b


def test_non_json_native_values_are_handled():
    checksum = compute_checksum({"date_of_birth": date(1990, 1, 1)})

    assert checksum == compute_checksum({"date_of_birth": date(1990, 1, 1)})
