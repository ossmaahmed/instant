"""Thin client for the booking and identity services.

Every call is real HTTP to the service URL from the environment. ApiError
carries the service's own Arabic message when one exists, or a generic
unavailable message when the service cannot be reached.
"""
import requests
from django.conf import settings


class ApiError(Exception):
    pass


class Unauthorized(ApiError):
    """The owner token was rejected: expired, revoked or never valid."""


def _call(method, base, path, token=None, **kwargs):
    headers = kwargs.pop('headers', {})
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        response = requests.request(method, base + path, headers=headers, timeout=settings.API_TIMEOUT, **kwargs)
    except requests.RequestException:
        raise ApiError('الخدمة مش متاحة دلوقتي. جرّب بعد شوية.')
    if response.status_code == 401 and token:
        raise Unauthorized('انتهت الجلسة. سجّل دخولك تاني.')
    if response.status_code == 403 and token:
        raise Unauthorized('مش مسموح بالدخول.')
    if response.status_code >= 400:
        try:
            message = response.json().get('error')
        except ValueError:
            message = None
        raise ApiError(message or 'حصل خطأ غير متوقع.')
    if response.status_code == 204:
        return None
    return response.json()


def _booking(method, path, **kwargs):
    return _call(method, settings.BOOKING_API_URL, path, **kwargs)


def _identity(method, path, **kwargs):
    return _call(method, settings.IDENTITY_API_URL, path, **kwargs)


# Public booking data
def services():
    return _booking('get', '/api/booking/services/')


def shop():
    return _booking('get', '/api/booking/shop/')


def schedules(days=3):
    return _booking('get', f'/api/booking/schedules/?days={days}')


def availability(day, service_pk):
    return _booking('get', f'/api/booking/availability/?day={day}&service={service_pk}')['slots']


# Guest booking flow
def create_booking(service, start, name, phone):
    return _booking('post', '/api/booking/bookings/', json={'service': service, 'start': start, 'name': name, 'phone': phone})


def lookup(code, phone, client_key):
    return _booking('post', '/api/booking/bookings/lookup/', json={'code': code, 'phone': phone, 'client_key': client_key})


def guest_availability(code, phone, day):
    return _booking('post', f'/api/booking/bookings/{code}/availability/', json={'phone': phone, 'day': day})['slots']


def guest_change(code, phone, start):
    return _booking('post', f'/api/booking/bookings/{code}/change/', json={'phone': phone, 'start': start})


def guest_cancel(code, phone):
    return _booking('post', f'/api/booking/bookings/{code}/cancel/', json={'phone': phone})


# Owner flow (token issued by the identity service)
def login(username, password):
    return _identity('post', '/api/identity/login/', json={'username': username, 'password': password})


def logout(token):
    return _identity('post', '/api/identity/logout/', token=token)


def change_password(token, old_password, new_password):
    return _identity('post', '/api/identity/password/', token=token, json={'old_password': old_password, 'new_password': new_password})


def owner_bookings(token, view='today'):
    return _booking('get', f'/api/booking/owner/bookings/?view={view}', token=token)


def owner_booking(token, pk):
    return _booking('get', f'/api/booking/owner/bookings/{pk}/', token=token)


def owner_create_booking(token, service, start, name, phone):
    return _booking('post', '/api/booking/owner/bookings/', token=token, json={'service': service, 'start': start, 'name': name, 'phone': phone})


def owner_change_booking(token, pk, start):
    return _booking('post', f'/api/booking/owner/bookings/{pk}/change/', token=token, json={'start': start})


def owner_set_status(token, pk, booking_status):
    return _booking('post', f'/api/booking/owner/bookings/{pk}/status/', token=token, json={'status': booking_status})


def owner_availability(token, pk, day):
    return _booking('get', f'/api/booking/owner/bookings/{pk}/availability/?day={day}', token=token)['slots']


def owner_schedules(token):
    return _booking('get', '/api/booking/owner/schedules/', token=token)


def owner_weekly(token):
    return _booking('get', '/api/booking/owner/weekly/', token=token)


def owner_save_weekly(token, days):
    return _booking('post', '/api/booking/owner/weekly/', token=token, json={'days': days})


def owner_save_schedule(token, day, opens, closes, closed):
    return _booking('post', '/api/booking/owner/schedules/', token=token, json={'day': day, 'opens': opens, 'closes': closes, 'closed': closed})


def owner_services(token):
    return _booking('get', '/api/booking/owner/services/', token=token)


def owner_save_service(token, data, pk=None):
    if pk:
        return _booking('patch', f'/api/booking/owner/services/{pk}/', token=token, json=data)
    return _booking('post', '/api/booking/owner/services/', token=token, json=data)


def owner_blocks(token):
    return _booking('get', '/api/booking/owner/blocks/', token=token)


def owner_add_block(token, day, start, end):
    return _booking('post', '/api/booking/owner/blocks/', token=token, json={'day': day, 'start': start, 'end': end})


def owner_remove_block(token, pk):
    return _booking('post', f'/api/booking/owner/blocks/{pk}/remove/', token=token)


def owner_update_shop(token, data):
    return _booking('patch', '/api/booking/owner/shop/', token=token, json=data)
