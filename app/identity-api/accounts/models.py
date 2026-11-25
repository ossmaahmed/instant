import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class OwnerToken(models.Model):
    # Only the SHA-256 hash is stored; the raw token is returned once at login.
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key_hash = models.CharField(max_length=64, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user):
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(user=user, key_hash=hash_token(raw), expires_at=timezone.now() + timedelta(hours=settings.TOKEN_TTL_HOURS))
        return raw, token

    @classmethod
    def authenticate(cls, raw):
        """Return the token's user if the token is known, unexpired and not
        revoked; otherwise None."""
        if not raw:
            return None
        token = cls.objects.filter(key_hash=hash_token(raw), revoked__isnull=True).first()
        if not token or token.expires_at <= timezone.now():
            return None
        return token.user

    def revoke(self):
        self.revoked = timezone.now()
        self.save(update_fields=['revoked'])


class LoginGuard(models.Model):
    key = models.CharField(max_length=70, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
