import requests
from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission


class IdentityUnavailable(APIException):
    status_code = 503
    default_detail = 'Identity service unavailable.'
    default_code = 'identity_unavailable'


class IsOwnerToken(BasePermission):
    """Owner-only endpoints: the bearer token must be verified by the
    identity service on every request, so lockout/logout revoke access
    immediately. Verification failures fail closed (503), never open."""

    def has_permission(self, request, view):
        header = request.headers.get('Authorization', '')
        token = header[7:] if header.startswith('Bearer ') else None
        if not token:
            return False
        try:
            response = requests.post(
                settings.IDENTITY_API_URL + '/api/identity/verify/',
                headers={'Authorization': f'Bearer {token}'},
                timeout=settings.IDENTITY_VERIFY_TIMEOUT,
            )
        except requests.RequestException:
            raise IdentityUnavailable()
        return response.status_code == 200
