"""PII redaction helpers shared across services and ops scripts."""


def mask_email(email: str) -> str:
    """Mask the local part, keeping the first character and full domain.

    ``ab@x.com`` → ``a***@x.com`` (not ``ab***``) so short locals do not
    leak almost the entire address in admin dashboards and CLI logs.
    """
    local, sep, domain = email.partition("@")
    if not sep or not local:
        return "***"
    return f"{local[0]}***@{domain}"
