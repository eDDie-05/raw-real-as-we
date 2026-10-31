from django.db.utils import OperationalError, ProgrammingError

from .cart import cart_count


def cart_context(request):
    try:
        count = cart_count(request)
    except (OperationalError, ProgrammingError):
        count = 0
    return {"raw_cart_count": count}
