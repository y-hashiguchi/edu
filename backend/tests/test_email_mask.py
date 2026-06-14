"""Tests for shared email masking."""

from app.core.email_mask import mask_email


def test_mask_email_redacts_short_local_part():
    assert mask_email("ab@x.com") == "a***@x.com"


def test_mask_email_redacts_long_local_part():
    assert mask_email("alice@example.com") == "a***@example.com"
    assert mask_email("student@e.com") == "s***@e.com"


def test_mask_email_single_char_local():
    assert mask_email("a@example.com") == "a***@example.com"


def test_mask_email_invalid():
    assert mask_email("garbage") == "***"
    assert mask_email("@nodomain.com") == "***"
