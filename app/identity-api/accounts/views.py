from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LoginGuard, OwnerToken, hash_token


def healthz(request):
    return JsonResponse({'ok': True})


def _bearer(request):
    header = request.headers.get('Authorization', '')
    return header[7:] if header.startswith('Bearer ') else None


class Login(APIView):
    """One guard protects the single owner account, including aliases/casing.
    Ten failed attempts lock login for LOCKOUT_MINUTES."""

    def post(self, request):
        with transaction.atomic():
            guard, _ = LoginGuard.objects.get_or_create(key='owner')
            guard = LoginGuard.objects.select_for_update().get(pk=guard.pk)
            now = timezone.now()
            if guard.locked_until and guard.locked_until > now:
                return Response({'error': 'الحساب مقفول مؤقتًا. جرّب بعد انتهاء مدة القفل.'}, status=status.HTTP_423_LOCKED)
            if guard.locked_until:
                guard.failures = 0
                guard.locked_until = None
            user = authenticate(request, username=str(request.data.get('username', ''))[:150], password=str(request.data.get('password', '')))
            if user and user.is_staff:
                guard.failures = 0
                guard.locked_until = None
                guard.save()
                raw, token = OwnerToken.issue(user)
                return Response({'token': raw, 'expires_at': token.expires_at.isoformat()})
            guard.failures += 1
            if guard.failures >= 10:
                guard.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                error = 'الحساب اتقفل مؤقتًا بعد ١٠ محاولات غلط.'
            else:
                error = 'اسم المستخدم أو كلمة السر مش صح.'
            guard.save()
        return Response({'error': error}, status=status.HTTP_401_UNAUTHORIZED)


class Logout(APIView):
    def post(self, request):
        raw = _bearer(request)
        user = OwnerToken.authenticate(raw)
        if user:
            OwnerToken.objects.get(key_hash=hash_token(raw)).revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)


class Verify(APIView):
    """Service-to-service token introspection. Other services call this on
    every owner request so logout, password change and lockout take effect
    immediately."""

    def post(self, request):
        user = OwnerToken.authenticate(_bearer(request))
        if not user or not user.is_active or not user.is_staff:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response({'username': user.username})


class PasswordChange(APIView):
    def post(self, request):
        raw = _bearer(request)
        user = OwnerToken.authenticate(raw)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        if not user.check_password(str(request.data.get('old_password', ''))):
            return Response({'error': 'كلمة السر الحالية مش صح.'}, status=status.HTTP_400_BAD_REQUEST)
        new_password = str(request.data.get('new_password', ''))
        try:
            validate_password(new_password, user)
        except ValidationError as exc:
            return Response({'error': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        # Every other session loses access; the one that changed the password stays.
        for token in OwnerToken.objects.filter(user=user, revoked__isnull=True).exclude(key_hash=hash_token(raw)):
            token.revoke()
        return Response({'ok': True})
