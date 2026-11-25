import time

from django.conf import settings

from . import api

_cache = {'shop': None, 'at': 0}


def _shop():
    # Shop details come from the booking service, cached briefly so a slow
    # moment there never breaks page rendering here.
    if time.monotonic() - _cache['at'] > 60:
        try:
            _cache['shop'] = api.shop()
            _cache['at'] = time.monotonic()
        except api.ApiError:
            _cache.setdefault('shop', None)
    return _cache['shop']


def common(request):
    return {
        'shop': _shop(),
        'owner_signed_in': bool(request.session.get('owner_token')),
        'development': settings.DEBUG,
        'cutoff': settings.CUSTOMER_CUTOFF_MINUTES,
        'lockout': settings.LOCKOUT_MINUTES,
        'step': settings.SLOT_STEP_MINUTES,
    }
