import pytest
from modules.utils import extract_order_id

@pytest.mark.parametrize("msg,expected", [
    ("Where is my order 12345?", "12345"),
    ("Track #9876", "9876"),
    ("order id 54321", "54321"),
])
def test_extract_order_id_found(msg, expected):
    assert extract_order_id(msg) == expected


def test_extract_order_id_none():
    assert extract_order_id("No numbers here") is None
