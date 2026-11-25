from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from unittest.mock import patch

from django.db import IntegrityError, connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .domain import RuleError, add_block, available, local_dt, phone_number, reserve, save_schedule, save_weekly, set_status
from .models import Booking, LookupGuard, Occupancy, Schedule, Service, WeeklyHours


class BookingTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate() + timedelta(days=1)
        self.s = Service.objects.create(name='قص شعر', price=120, duration=30)
        Schedule.objects.create(day=self.day, opens=time(10), closes=time(22))
        self.start = local_dt(self.day, time(12))

    def make(self, **kw):
        args = dict(service=self.s, start=self.start, name='زبون تجريبي', phone='01000000000')
        args.update(kw)
        return reserve(**args)

    def test_booking_persists_with_minute_database_claims(self):
        b = self.make()
        self.assertEqual(Booking.objects.get(pk=b.pk).name, 'زبون تجريبي')
        self.assertEqual(b.occupancy_set.count(), 30)

    def test_overlap_rejected_even_different_duration(self):
        self.s.duration = 60
        self.s.save()
        self.make()
        with self.assertRaises(RuleError):
            self.make(start=self.start + timedelta(minutes=30))
        self.assertEqual(Booking.objects.count(), 1)

    def test_unique_constraint_enforced_without_domain(self):
        b = self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Occupancy.objects.create(minute=self.start, booking=b)

    def test_adjacent_allowed(self):
        self.make()
        self.make(start=self.start + timedelta(minutes=30))
        self.assertEqual(Booking.objects.count(), 2)

    def test_window_fixed_two_days(self):
        day = timezone.localdate() + timedelta(days=3)
        Schedule.objects.create(day=day)
        with self.assertRaises(RuleError):
            self.make(start=local_dt(day, time(12)))

    def test_day_off_and_missing_day_rejected(self):
        Schedule.objects.filter(day=self.day).update(closed=True)
        self.assertEqual(available(self.s, self.day), [])
        with self.assertRaises(RuleError):
            self.make()
        Schedule.objects.all().delete()
        with self.assertRaises(RuleError):
            self.make()

    def test_duration_end_boundary_and_grid(self):
        with self.assertRaises(RuleError):
            self.make(start=local_dt(self.day, time(21, 45)))
        with self.assertRaises(RuleError):
            self.make(start=local_dt(self.day, time(22)))
        self.make(start=local_dt(self.day, time(21, 30)))

    def test_cancel_releases_slot(self):
        b = self.make()
        set_status(b, 'cancelled')
        self.make()
        self.assertEqual(Occupancy.objects.count(), 30)

    def test_atomic_failed_move_preserves_old_reservation(self):
        b = self.make()
        self.make(start=self.start + timedelta(hours=1))
        with self.assertRaises(RuleError):
            self.make(booking=b, start=self.start + timedelta(hours=1))
        b.refresh_from_db()
        self.assertEqual(b.start, self.start)
        self.assertEqual(b.occupancy_set.count(), 30)

    def test_move_preserves_price_duration_snapshot(self):
        b = self.make()
        self.s.duration = 60
        self.s.price = 999
        self.s.save()
        self.make(booking=b, start=self.start + timedelta(hours=1))
        b.refresh_from_db()
        self.assertEqual(b.duration, 30)
        self.assertEqual(b.price, 120)

    def test_change_cutoff(self):
        b = self.make()
        with patch('booking.domain.timezone.now', return_value=self.start - timedelta(minutes=119)):
            with self.assertRaises(RuleError):
                set_status(b, 'cancelled')
            set_status(b, 'cancelled', owner=True)

    def test_exact_cutoff_allowed(self):
        b = self.make()
        with patch('booking.domain.timezone.now', return_value=self.start - timedelta(hours=2)):
            set_status(b, 'cancelled')

    def test_completed_and_no_show_cannot_be_future(self):
        b = self.make()
        with self.assertRaises(RuleError):
            set_status(b, 'completed', owner=True)

    def test_hours_conflict_rejects_without_cancelling(self):
        b = self.make()
        with self.assertRaises(RuleError):
            save_schedule(self.day, time(13), time(22), False)
        with self.assertRaises(RuleError):
            save_schedule(self.day, time(10), time(22), True)
        self.assertFalse(Schedule.objects.get(day=self.day).closed)
        b.refresh_from_db()
        self.assertEqual(b.status, 'confirmed')

    def test_owner_hours_immediately_drive_availability(self):
        save_schedule(self.day, time(14), time(16), False)
        self.assertEqual(timezone.localtime(available(self.s, self.day)[0]).time(), time(14))
        save_schedule(self.day, time(14), time(16), True)
        self.assertEqual(available(self.s, self.day), [])

    def test_block_conflict_and_release(self):
        block = add_block(self.day, self.start, self.start + timedelta(hours=1))
        with self.assertRaises(RuleError):
            self.make()
        block.delete()
        self.make()
        with self.assertRaises(RuleError):
            add_block(self.day, self.start, self.start + timedelta(minutes=30))

    def test_phone_validation_and_normalization(self):
        self.assertEqual(phone_number('+201000000000'), '01000000000')
        self.assertEqual(phone_number('٠١٠٠٠٠٠٠٠٠٠'), '01000000000')
        with self.assertRaises(RuleError):
            phone_number('0123')

    def test_disabled_service_prevents_new_booking(self):
        self.s.active = False
        self.s.save()
        with self.assertRaises(RuleError):
            self.make()


class ApiTests(TestCase):
    """API-level behavior: public guest flow, lookup guard, and owner
    authorization enforced through the identity service."""

    def setUp(self):
        self.client = APIClient()
        self.day = timezone.localdate() + timedelta(days=1)
        self.s = Service.objects.create(name='قص شعر', price=120, duration=30)
        Schedule.objects.create(day=self.day, opens=time(10), closes=time(22))
        self.start = local_dt(self.day, time(12))

    def create_booking(self):
        r = self.client.post('/api/booking/bookings/', {
            'service': self.s.pk, 'start': self.start.isoformat(),
            'name': 'عميل جديد', 'phone': '01000000000',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_guest_booking_flow_over_api(self):
        data = self.create_booking()
        self.assertEqual(data['name'], 'عميل جديد')
        self.assertEqual(data['service_name'], 'قص شعر')
        # Same slot again must conflict.
        r = self.client.post('/api/booking/bookings/', {
            'service': self.s.pk, 'start': self.start.isoformat(),
            'name': 'تاني', 'phone': '01000000000',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_public_lists_hide_inactive_and_expose_hours(self):
        Service.objects.create(name='خدمة مقفولة', price=50, duration=30, active=False)
        services = self.client.get('/api/booking/services/').json()
        self.assertEqual([s['name'] for s in services], ['قص شعر'])
        schedules = self.client.get('/api/booking/schedules/?days=3').json()
        self.assertEqual(schedules[0]['day'], self.day.isoformat())
        self.assertEqual(self.client.get('/api/booking/availability/').json(), {'slots': []})
        slots = self.client.get(f'/api/booking/availability/?day={self.day.isoformat()}&service={self.s.pk}').json()['slots']
        self.assertIn(self.start.isoformat(), slots)

    def test_lookup_requires_code_and_phone_and_is_limited(self):
        data = self.create_booking()
        r = self.client.post('/api/booking/bookings/lookup/', {'code': data['code'], 'phone': '01100000000', 'client_key': 's1'}, format='json')
        self.assertEqual(r.status_code, 404)
        r = self.client.post('/api/booking/bookings/lookup/', {'code': data['code'], 'phone': '01000000000', 'client_key': 's1'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LookupGuard.objects.get(key='lookup:s1').failures, 0)
        for _ in range(10):
            self.client.post('/api/booking/bookings/lookup/', {'code': 'WRONG', 'phone': '01000000000', 'client_key': 's2'}, format='json')
        guard = LookupGuard.objects.get(key='lookup:s2')
        self.assertIsNotNone(guard.locked_until)
        self.assertAlmostEqual((guard.locked_until - timezone.now()).total_seconds(), 900, delta=5)
        r = self.client.post('/api/booking/bookings/lookup/', {'code': data['code'], 'phone': '01000000000', 'client_key': 's2'}, format='json')
        self.assertEqual(r.status_code, 400)  # locked message even with correct data
        # Expired lock resets the counter.
        LookupGuard.objects.filter(key='lookup:s2').update(locked_until=timezone.now() - timedelta(seconds=1))
        self.client.post('/api/booking/bookings/lookup/', {'code': 'WRONG', 'phone': '01000000000', 'client_key': 's2'}, format='json')
        self.assertEqual(LookupGuard.objects.get(key='lookup:s2').failures, 1)

    def test_guest_change_and_cancel_with_cutoff(self):
        data = self.create_booking()
        new_start = self.start + timedelta(hours=1)
        r = self.client.post(f"/api/booking/bookings/{data['code']}/change/", {'phone': '01000000000', 'start': new_start.isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Booking.objects.get(code=data['code']).start, new_start)
        # Wrong phone cannot touch the booking.
        r = self.client.post(f"/api/booking/bookings/{data['code']}/cancel/", {'phone': '01100000000'}, format='json')
        self.assertEqual(r.status_code, 404)
        r = self.client.post(f"/api/booking/bookings/{data['code']}/cancel/", {'phone': '01000000000'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Booking.objects.get(code=data['code']).status, 'cancelled')
        self.assertEqual(Occupancy.objects.count(), 0)

    def test_owner_endpoints_require_verified_token(self):
        for url in ['/api/booking/owner/bookings/', '/api/booking/owner/schedules/', '/api/booking/owner/services/', '/api/booking/owner/blocks/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        # A token the identity service rejects is denied.
        with patch('booking.permissions.requests.post') as verify:
            verify.return_value.status_code = 401
            self.assertEqual(self.client.get('/api/booking/owner/bookings/', HTTP_AUTHORIZATION='Bearer bad').status_code, 403)
        # A verified token reaches the data.
        with patch('booking.permissions.requests.post') as verify:
            verify.return_value.status_code = 200
            self.create_booking()
            r = self.client.get('/api/booking/owner/bookings/?view=all', HTTP_AUTHORIZATION='Bearer good')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()[0]['name'], 'عميل جديد')

    def test_owner_manual_booking_and_status_over_api(self):
        with patch('booking.permissions.requests.post') as verify:
            verify.return_value.status_code = 200
            auth = {'HTTP_AUTHORIZATION': 'Bearer good'}
            r = self.client.post('/api/booking/owner/bookings/', {
                'service': self.s.pk, 'start': self.start.isoformat(),
                'name': 'حجز يدوي', 'phone': '01000000000',
            }, format='json', **auth)
            self.assertEqual(r.status_code, 201, r.content)
            pk = r.json()['pk']
            with self.assertRaises(RuleError):
                set_status(Booking.objects.get(pk=pk), 'completed', owner=True)
            r = self.client.post(f'/api/booking/owner/bookings/{pk}/status/', {'status': 'cancelled'}, format='json', **auth)
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(Booking.objects.get(pk=pk).status, 'cancelled')

    def test_owner_schedule_conflict_rejected_over_api(self):
        with patch('booking.permissions.requests.post') as verify:
            verify.return_value.status_code = 200
            auth = {'HTTP_AUTHORIZATION': 'Bearer good'}
            self.create_booking()
            r = self.client.post('/api/booking/owner/schedules/', {
                'day': self.day.isoformat(), 'opens': '13:00', 'closes': '22:00', 'closed': False,
            }, format='json', **auth)
            self.assertEqual(r.status_code, 400)
            self.assertFalse(Schedule.objects.get(day=self.day).closed)
            self.assertEqual(Booking.objects.count(), 1)

    def test_owner_hours_and_block_flow_over_api(self):
        with patch('booking.permissions.requests.post') as verify:
            verify.return_value.status_code = 200
            auth = {'HTTP_AUTHORIZATION': 'Bearer good'}
            r = self.client.post('/api/booking/owner/schedules/', {
                'day': self.day.isoformat(), 'opens': '14:00', 'closes': '16:00', 'closed': False,
            }, format='json', **auth)
            self.assertEqual(r.status_code, 200, r.content)
            slots = self.client.get(f'/api/booking/availability/?day={self.day.isoformat()}&service={self.s.pk}').json()['slots']
            self.assertEqual(timezone.localtime(__import__('datetime').datetime.fromisoformat(slots[0])).time(), time(14))
            r = self.client.post('/api/booking/owner/blocks/', {
                'day': self.day.isoformat(), 'start': '14:00', 'end': '15:00',
            }, format='json', **auth)
            self.assertEqual(r.status_code, 201, r.content)
            block_pk = r.json()['pk']
            r = self.client.post('/api/booking/owner/blocks/', {
                'day': self.day.isoformat(), 'start': '14:30', 'end': '15:30',
            }, format='json', **auth)
            self.assertEqual(r.status_code, 400)  # overlapping block rejected
            r = self.client.post(f'/api/booking/owner/blocks/{block_pk}/remove/', **auth)
            self.assertEqual(r.status_code, 204)
            self.assertEqual(Occupancy.objects.filter(block__isnull=False).count(), 0)


class ConcurrencyTests(TransactionTestCase):
    def test_two_parallel_requests_only_one_wins(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL concurrency test runs in CI with a PostgreSQL service')
        day = timezone.localdate() + timedelta(days=1)
        Schedule.objects.create(day=day)
        s = Service.objects.create(name='Hair', price=100, duration=60)
        start = local_dt(day, time(12))

        def attempt(i):
            try:
                reserve(service=Service.objects.get(pk=s.pk), start=start, name='Test guest', phone='01000000000')
                return True
            except RuleError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Occupancy.objects.count(), 60)


class WeeklyHoursTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate() + timedelta(days=1)
        self.s = Service.objects.create(name='قص شعر', price=120, duration=30)

    def save_all(self, overrides=None):
        rows = []
        for i in range(7):
            row = {'weekday': i, 'opens': time(10), 'closes': time(22), 'closed': False}
            row.update((overrides or {}).get(i, {}))
            rows.append(row)
        save_weekly(rows)

    def test_weekly_template_drives_availability(self):
        self.save_all()
        slots = available(self.s, self.day)
        assert slots, 'weekly-governed day should be bookable'
        b = reserve(service=self.s, start=slots[0], name='زبون تجريبي', phone='01000000000')
        assert b.pk
        # cancel path (locks weekly row when no dated row exists)
        set_status(b, 'cancelled')
        assert Booking.objects.get(pk=b.pk).status == 'cancelled'

    def test_dated_override_beats_weekly(self):
        self.save_all()
        assert available(self.s, self.day)
        save_schedule(self.day, time(10), time(22), True)  # holiday on this date
        assert available(self.s, self.day) == []
        save_schedule(self.day, time(14), time(20), False)  # shorter hours on this date
        slots = available(self.s, self.day)
        assert slots and timezone.localtime(slots[0]).time() == time(14)
        # weekly row itself untouched
        w = WeeklyHours.objects.get(weekday=self.day.weekday())
        assert (w.opens, w.closed) == (time(10), False)

    def test_weekly_closed_weekday_not_bookable(self):
        self.save_all({self.day.weekday(): {'closed': True}})
        assert available(self.s, self.day) == []

    def test_weekly_save_refused_when_cutting_existing_booking(self):
        self.save_all()
        slot = available(self.s, self.day)[0]
        reserve(service=self.s, start=slot, name='زبون تجريبي', phone='01000000000')
        with self.assertRaises(RuleError):
            self.save_all({self.day.weekday(): {'closed': True}})
        # booking untouched
        assert Booking.objects.filter(status='confirmed').count() == 1

    def test_weekly_save_ignores_dates_with_dated_overrides(self):
        Schedule.objects.create(day=self.day, opens=time(10), closes=time(22))
        slot = available(self.s, self.day)[0]
        reserve(service=self.s, start=slot, name='زبون تجريبي', phone='01000000000')
        # closing the weekday in the template must not touch the overridden date
        self.save_all({self.day.weekday(): {'closed': True}})
        assert available(self.s, self.day), 'dated override still governs'

    def test_block_on_weekly_day_snapshots_template(self):
        self.save_all()
        start = local_dt(self.day, time(13))
        b = add_block(self.day, start, start + timedelta(hours=1))
        assert b.pk
        s = Schedule.objects.get(day=self.day)
        assert (s.opens, s.closes) == (time(10), time(22))

    def test_seed_preserves_existing_data_and_skips_weekly(self):
        from django.core.management import call_command
        Schedule.objects.create(day=self.day, opens=time(9), closes=time(21), closed=True)
        call_command('seed_demo')
        assert not WeeklyHours.objects.exists(), 'seed must not invent hours on an existing install'
        assert Schedule.objects.get(day=self.day).closed  # existing rows untouched

    def test_seed_creates_weekly_only_on_fresh_install(self):
        from django.core.management import call_command
        call_command('seed_demo')
        assert WeeklyHours.objects.count() == 7
        assert not Schedule.objects.exists(), 'fresh seed uses the rolling template, not fixed dates'


class WeeklyApiTests(TestCase):
    def test_owner_weekly_roundtrip_over_api(self):
        from unittest.mock import patch as _patch
        c = APIClient()
        days = [{'weekday': i, 'opens': '10:00', 'closes': '22:00', 'closed': (i == 4)} for i in range(7)]
        with _patch('booking.permissions.IsOwnerToken.has_permission', return_value=True):
            r = c.post('/api/booking/owner/weekly/', {'days': days}, format='json', HTTP_AUTHORIZATION='Bearer x')
            assert r.status_code == 200, r.content[:200]
            r = c.get('/api/booking/owner/weekly/', HTTP_AUTHORIZATION='Bearer x')
            assert r.status_code == 200
        data = r.json()
        assert len(data) == 7
        assert next(d for d in data if d['weekday'] == 4)['closed'] is True
        # public schedules now reflect the template for dates without overrides
        day = timezone.localdate() + timedelta(days=6)
        r = c.get('/api/booking/schedules/?days=7')
        rows = {x['day']: x for x in r.json()}
        assert day.isoformat() in rows, 'weekly-governed date must appear publicly'

    def test_owner_weekly_requires_token(self):
        c = APIClient()
        assert c.get('/api/booking/owner/weekly/').status_code in (401, 403)
