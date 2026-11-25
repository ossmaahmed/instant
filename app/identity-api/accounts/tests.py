from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import LoginGuard, OwnerToken


class IdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = get_user_model().objects.create_user('owner', password='correct-horse-42', is_staff=True)

    def login(self, username='owner', password='correct-horse-42'):
        return self.client.post('/api/identity/login/', {'username': username, 'password': password}, format='json')

    def test_login_issues_usable_token(self):
        r = self.login()
        self.assertEqual(r.status_code, 200, r.content)
        token = r.json()['token']
        r = self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['username'], 'owner')
        # Only the hash is stored; the raw token appears nowhere in the table.
        self.assertNotIn(token, str(OwnerToken.objects.values()))

    def test_wrong_password_and_unknown_or_revoked_token(self):
        self.assertEqual(self.login(password='wrong').status_code, 401)
        self.assertEqual(self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION='Bearer nope').status_code, 401)
        token = self.login().json()['token']
        self.client.post('/api/identity/logout/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 401)

    def test_expired_token_rejected(self):
        token = self.login().json()['token']
        OwnerToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 401)

    def test_nonstaff_user_cannot_get_owner_token(self):
        get_user_model().objects.create_user('guest', password='guest-pass-42', is_staff=False)
        self.assertEqual(self.login('guest', 'guest-pass-42').status_code, 401)

    def test_ten_failures_lock_and_expiry(self):
        for _ in range(9):
            self.login(password='invalid')
        self.assertIsNone(LoginGuard.objects.get(key='owner').locked_until)
        self.login(password='invalid')
        guard = LoginGuard.objects.get(key='owner')
        self.assertIsNotNone(guard.locked_until)
        self.assertAlmostEqual((guard.locked_until - timezone.now()).total_seconds(), 900, delta=5)
        # While locked, even the correct password is refused.
        r = self.login()
        self.assertEqual(r.status_code, 423)
        self.assertEqual(LoginGuard.objects.get(key='owner').failures, 10)
        # After the lock expires, counters reset and a correct login works.
        LoginGuard.objects.filter(key='owner').update(locked_until=timezone.now() - timedelta(seconds=1))
        self.login(password='invalid')
        self.assertEqual(LoginGuard.objects.get(key='owner').failures, 1)
        self.assertEqual(self.login().status_code, 200)

    def test_password_change_revokes_other_tokens(self):
        token_a = self.login().json()['token']
        token_b = self.login().json()['token']
        r = self.client.post('/api/identity/password/', {'old_password': 'correct-horse-42', 'new_password': 'new-secret-99'}, format='json', HTTP_AUTHORIZATION=f'Bearer {token_a}')
        self.assertEqual(r.status_code, 200, r.content)
        # The token that changed the password stays; every other token dies.
        self.assertEqual(self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION=f'Bearer {token_a}').status_code, 200)
        self.assertEqual(self.client.post('/api/identity/verify/', HTTP_AUTHORIZATION=f'Bearer {token_b}').status_code, 401)
        # The old password no longer works; the new one does.
        self.assertEqual(self.login(password='correct-horse-42').status_code, 401)
        self.assertEqual(self.login(password='new-secret-99').status_code, 200)

    def test_password_change_rejects_wrong_current_and_weak_new(self):
        token = self.login().json()['token']
        r = self.client.post('/api/identity/password/', {'old_password': 'nope', 'new_password': 'new-secret-99'}, format='json', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/identity/password/', {'old_password': 'correct-horse-42', 'new_password': '12345678'}, format='json', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.post('/api/identity/password/', {'old_password': 'correct-horse-42', 'new_password': 'new-secret-99'}, format='json').status_code, 401)
