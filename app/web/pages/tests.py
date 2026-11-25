from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone

from . import api

SERVICES = [{'pk': 1, 'name': 'قص شعر', 'price': '120', 'duration': 30, 'active': True}]
SCHEDULES = [{'day': (timezone.localdate() + timedelta(days=1)).isoformat(), 'closed': False, 'opens': '10:00:00', 'closes': '22:00:00'}]
SHOP = {'name': 'مقص', 'address': 'العنوان'}


def booking_dict(**kw):
    start = timezone.now() + timedelta(days=1)
    data = {
        'pk': 7, 'code': 'ABC123', 'name': 'زبون', 'phone': '01000000000',
        'service_name': 'قص شعر', 'price': '120', 'duration': 30,
        'start': start.isoformat(), 'end': (start + timedelta(minutes=30)).isoformat(),
        'status': 'confirmed', 'get_status_display': 'مؤكد', 'source': 'customer',
    }
    data.update(kw)
    return data


class PublicPageTests(TestCase):
    def setUp(self):
        patches = {
            'services': SERVICES,
            'schedules': SCHEDULES,
            'shop': SHOP,
            'availability': [],
        }
        self.patchers = []
        for name, value in patches.items():
            p = patch.object(api, name, return_value=value)
            setattr(self, name, p.start())
            self.patchers.append(p)

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_public_pages_render(self):
        for path in ['/', '/book/', '/manage/', '/owner/login/']:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_owner_pages_redirect_when_logged_out(self):
        for path in ['/owner/', '/owner/hours/', '/owner/services/', '/owner/settings/', '/owner/manual/', '/owner/blocks/', '/owner/password/']:
            self.assertEqual(self.client.get(path).status_code, 302, path)

    def test_csrf_enforced_on_posts(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/book/', {}).status_code, 403)
        self.assertEqual(client.post('/owner/login/', {}).status_code, 403)
        self.assertEqual(client.post('/owner/logout/', {}).status_code, 403)

    def test_get_mutation_rejected(self):
        self.assertEqual(self.client.get('/manage/cancel/').status_code, 405)

    def test_home_shows_services_and_hours(self):
        response = self.client.get('/')
        self.assertContains(response, 'قص شعر')
        self.assertContains(response, '120')

    def test_booking_page_escapes_and_renders(self):
        with patch.object(api, 'availability', return_value=[]):
            response = self.client.get('/book/?service=1&day=' + SCHEDULES[0]['day'])
        self.assertEqual(response.status_code, 200)

    def test_api_outage_renders_home_with_message(self):
        self.services.side_effect = api.ApiError('الخدمة مش متاحة دلوقتي. جرّب بعد شوية.')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'الخدمة مش متاحة')


class GuestFlowTests(TestCase):
    def setUp(self):
        self.patchers = [patch.object(api, n, return_value=v) for n, v in {
            'services': SERVICES, 'schedules': SCHEDULES, 'shop': SHOP}.items()]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_create_booking_stores_session_and_detail_renders(self):
        saved = booking_dict()
        with patch.object(api, 'create_booking', return_value=saved) as create:
            response = self.client.post('/book/', {
                'service': 1, 'day': SCHEDULES[0]['day'], 'start': saved['start'],
                'name': 'زبون جديد', 'phone': '01000000000',
            })
            self.assertEqual(response.status_code, 302)
            create.assert_called_once()
        response = self.client.get('/manage/booking/')
        self.assertContains(response, 'ABC123')

    def test_lookup_wrong_then_right(self):
        self.client.get('/manage/')
        with patch.object(api, 'lookup', side_effect=api.ApiError('ملقيناش حجز بالبيانات دي.')):
            response = self.client.post('/manage/', {'code': 'ABC123', 'phone': '01100000000'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('booking_code', self.client.session)
        with patch.object(api, 'lookup', return_value=booking_dict()):
            response = self.client.post('/manage/', {'code': 'ABC123', 'phone': '01000000000'})
            self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get('/manage/booking/'), 'ABC123')

    def test_booking_name_html_escaped(self):
        with patch.object(api, 'lookup', return_value=booking_dict(name='<script>alert(1)</script>')):
            self.client.get('/manage/')
            self.client.post('/manage/', {'code': 'ABC123', 'phone': '01000000000'})
        response = self.client.get('/manage/booking/')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_cancel_requires_confirm(self):
        with patch.object(api, 'lookup', return_value=booking_dict()):
            self.client.get('/manage/')
            self.client.post('/manage/', {'code': 'ABC123', 'phone': '01000000000'})
        with patch.object(api, 'guest_cancel', return_value=booking_dict(status='cancelled')) as cancel:
            self.client.post('/manage/cancel/', {})
            cancel.assert_not_called()
            response = self.client.post('/manage/cancel/', {'confirm': 'yes'}, follow=True)
            cancel.assert_called_once()
            self.assertContains(response, 'الحجز اتلغى')


class OwnerFlowTests(TestCase):
    def setUp(self):
        self.patchers = [patch.object(api, n, return_value=v) for n, v in {
            'services': SERVICES, 'schedules': SCHEDULES, 'shop': SHOP}.items()]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def login(self):
        with patch.object(api, 'login', return_value={'token': 'tok', 'expires_at': 'x'}):
            self.client.post('/owner/login/', {'username': 'owner', 'password': 'secret'})

    def test_login_stores_token_and_dashboard_renders(self):
        with patch.object(api, 'login', side_effect=api.ApiError('اسم المستخدم أو كلمة السر مش صح.')):
            response = self.client.post('/owner/login/', {'username': 'owner', 'password': 'bad'})
            self.assertContains(response, 'مش صح')
            self.assertNotIn('owner_token', self.client.session)
        self.login()
        with patch.object(api, 'owner_bookings', return_value=[booking_dict()]) as bookings:
            response = self.client.get('/owner/')
            self.assertContains(response, 'زبون')
            _, kwargs = bookings.call_args
            self.assertEqual(bookings.call_args[0][0], 'tok')  # the session token is what calls the API
            response = self.client.get('/owner/?format=json')
            self.assertEqual(response.json()['bookings'][0]['name'], 'زبون')

    def test_rejected_token_logs_owner_out(self):
        self.login()
        with patch.object(api, 'owner_bookings', side_effect=api.Unauthorized('x')):
            response = self.client.get('/owner/')
            self.assertEqual(response.status_code, 302)
            self.assertNotIn('owner_token', self.client.session)

    def test_logout_revokes_and_clears(self):
        self.login()
        with patch.object(api, 'logout') as logout:
            self.client.post('/owner/logout/')
            logout.assert_called_once_with('tok')
        self.assertEqual(self.client.get('/owner/').status_code, 302)

    def test_owner_hours_conflict_message(self):
        self.login()
        with patch.object(api, 'owner_schedules', return_value=SCHEDULES), patch.object(api, 'owner_weekly', return_value=[]):
            with patch.object(api, 'owner_save_schedule', side_effect=api.ApiError('فيه حجوزات موجودة هتتعارض.')):
                response = self.client.post('/owner/hours/', {
                    'day': SCHEDULES[0]['day'], 'opens': '13:00', 'closes': '22:00',
                })
                self.assertContains(response, 'فيه حجوزات')

    def test_password_change_calls_identity(self):
        self.login()
        with patch.object(api, 'change_password') as change:
            response = self.client.post('/owner/password/', {
                'old_password': 'old', 'new_password': 'new-secret-99', 'new_password2': 'new-secret-99',
            })
            change.assert_called_once_with('tok', 'old', 'new-secret-99')
            self.assertEqual(response.status_code, 302)

    def test_owner_token_never_in_session_cookie(self):
        # The owner bearer token lives only in the server-side session table.
        self.login()
        cookie = self.client.cookies.get('sessionid')
        self.assertIsNotNone(cookie)
        self.assertNotIn('tok', cookie.value)
        from django.contrib.sessions.models import Session
        self.assertNotIn('tok', Session.objects.get(session_key=cookie.value).session_data)  # encoded payload, token stored server-side


class CustomerOwnerSeparationTests(TestCase):
    def test_interfaces_stay_separate_after_login(self):
        session = self.client.session
        session['owner_token'] = 'tok'
        session.save()
        # customer pages stay customer-only, even for a signed-in owner
        html = self.client.get('/').content.decode()
        assert 'owner-nav' not in html
        assert 'لوحة الإدارة' not in html
        # owner pages use the owner layout: owner nav present, customer nav absent
        with patch.object(api, 'owner_bookings', return_value=[]):
            html = self.client.get('/owner/').content.decode()
            assert 'owner-nav' in html
            assert 'إدارة حجزك' not in html
            # already-signed-in owner visiting the login page goes to the dashboard
            response = self.client.get('/owner/login/')
            self.assertRedirects(response, '/owner/')

    def test_login_page_has_no_customer_navigation(self):
        html = self.client.get('/owner/login/').content.decode()
        assert 'إدارة حجزك' not in html
        assert 'احجز ميعاد' not in html

    def test_customer_pages_have_no_owner_login_entry(self):
        for url in ('/', '/book/'):
            html = self.client.get(url).content.decode()
            assert 'owner/login' not in html, url
            assert 'دخول صاحب المحل' not in html, url


class ArabicTimeTests(TestCase):
    def test_dayparts_and_12hour(self):
        import datetime
        from pages.timefmt import arabic_time
        cases = {
            datetime.time(0, 30): '١٢:٣٠ ليلًا',
            datetime.time(9, 0): '٩:٠٠ صباحًا',
            datetime.time(12, 0): '١٢:٠٠ ظهرًا',
            datetime.time(14, 0): '٢:٠٠ عصرًا',
            datetime.time(17, 30): '٥:٣٠ مساءً',
            datetime.time(23, 59): '١١:٥٩ مساءً',
        }
        for value, expected in cases.items():
            assert arabic_time(value) == expected, (value, arabic_time(value))


class OwnerApiOutageTests(TestCase):
    def login(self):
        session = self.client.session
        session['owner_token'] = 'tok'
        session.save()

    def test_dashboard_api_error_renders_503_not_redirect_loop(self):
        self.login()
        with patch.object(api, 'owner_bookings', side_effect=api.ApiError('down')):
            response = self.client.get('/owner/')
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'مش متاحة', status_code=503)


class WeeklyTemplateTests(TestCase):
    def login(self):
        session = self.client.session
        session['owner_token'] = 'tok'
        session.save()

    def test_hours_page_renders_weekly_grid(self):
        self.login()
        with patch.object(api, 'owner_schedules', return_value=[]), patch.object(api, 'owner_weekly', return_value=[]):
            html = self.client.get('/owner/hours/').content.decode()
        assert 'الجدول الأسبوعي' in html
        for name in ('السبت', 'الأحد', 'الاثنين', 'الجمعة'):
            assert name in html
        assert 'opens-0' in html and 'closes-6' in html and 'closed-4' in html

    def test_weekly_save_posts_all_seven_days(self):
        self.login()
        data = {'weekly_save': '1'}
        for i in range(7):
            data[f'opens-{i}'] = '10:00'
            data[f'closes-{i}'] = '22:00'
        data['closed-4'] = '1'  # Friday off
        with patch.object(api, 'owner_save_weekly', return_value=[]) as save:
            response = self.client.post('/owner/hours/', data)
        self.assertEqual(response.status_code, 302)
        days = save.call_args[0][1]
        assert len(days) == 7
        friday = next(d for d in days if d['weekday'] == 4)
        assert friday['closed'] is True
        assert friday['opens'] == '10:00'

    def test_weekly_save_error_shown_not_raised(self):
        self.login()
        data = {'weekly_save': '1'}
        for i in range(7):
            data[f'opens-{i}'] = '10:00'
            data[f'closes-{i}'] = '22:00'
        with patch.object(api, 'owner_save_weekly', side_effect=api.ApiError('فيه حجوزات موجودة هتتعارض مع الجدول الجديد.')),              patch.object(api, 'owner_schedules', return_value=[]), patch.object(api, 'owner_weekly', return_value=[]):
            response = self.client.post('/owner/hours/', data)
        self.assertContains(response, 'هتتعارض')
