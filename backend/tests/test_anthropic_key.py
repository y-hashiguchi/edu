from app.config import Settings, normalize_api_key


def test_clean_key_is_unchanged() -> None:
    key = "sk-ant-api03-" + "x" * 90

    assert normalize_api_key(key) == key


def test_trailing_newline_is_stripped() -> None:
    # Render's env-var textarea readily appends a trailing newline on paste,
    # which httpx rejects as an "Illegal header value" in the Authorization
    # header -> anthropic.APIConnectionError -> chat 502.
    key = "sk-ant-api03-abc"

    assert normalize_api_key(key + "\n") == key


def test_surrounding_whitespace_is_stripped() -> None:
    key = "sk-ant-api03-abc"

    assert normalize_api_key("  " + key + " \r\n") == key


def test_embedded_cr_lf_is_removed() -> None:
    # A genuine Anthropic key never contains whitespace; an embedded CR/LF can
    # only come from a corrupted paste, so we strip it rather than ship a header
    # value that httpx will refuse to send.
    assert normalize_api_key("sk-ant-\r\napi03-abc") == "sk-ant-api03-abc"


def test_empty_key_is_unchanged() -> None:
    # Stub mode (CI / E2E) leaves the key empty; normalization must not turn
    # that into anything truthy.
    assert normalize_api_key("") == ""


def test_settings_normalizes_api_key_from_env() -> None:
    # End-to-end of the field_validator wiring: a dirty value (as a Render env
    # var might supply) must be cleaned before the Anthropic client sees it.
    settings = Settings(
        jwt_secret_key="test-secret",
        anthropic_api_key="sk-ant-api03-abc\n",
    )

    assert settings.anthropic_api_key == "sk-ant-api03-abc"
