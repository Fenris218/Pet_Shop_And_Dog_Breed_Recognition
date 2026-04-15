from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def vnd_format(value):
    """Format number as VND with dot thousand separators (e.g. 9.000.000)."""
    if value is None or value == "":
        return "0"

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    return f"{int(number):,}".replace(",", ".")
