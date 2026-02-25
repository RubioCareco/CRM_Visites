import re


def normalize_siret(raw_value: str) -> str:
    """Keep digits only and enforce max 14 chars."""
    return re.sub(r"\D", "", raw_value or "")[:14]


def is_luhn_valid(number: str) -> bool:
    """Return True when the provided numeric string passes Luhn checksum."""
    if not number or not number.isdigit():
        return False
    total = 0
    reverse_digits = number[::-1]
    for idx, char in enumerate(reverse_digits):
        digit = int(char)
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def validate_siret(raw_value: str):
    """
    Validate SIRET format/checksum.
    Returns tuple: (is_valid, cleaned_siret, error_message).
    Empty values are accepted to preserve current optional field behavior.
    """
    cleaned = normalize_siret(raw_value)
    if not cleaned:
        return True, "", ""
    if len(cleaned) != 14:
        return False, cleaned, "Numéro SIRET invalide : 14 chiffres requis."
    if not is_luhn_valid(cleaned):
        return False, cleaned, "Numéro SIRET invalide : contrôle Luhn échoué."
    return True, cleaned, ""
