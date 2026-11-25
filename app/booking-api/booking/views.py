from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .domain import RuleError, add_block, available, can_change, effective_schedule, local_dt, phone_number, reserve, save_schedule, save_weekly, set_status
from .models import Block, Booking, LookupGuard, Schedule, Service, Shop, WeeklyHours
from .permissions import IsOwnerToken
from .serializers import BlockSerializer, BookingSerializer, ScheduleSerializer, ServiceSerializer, ShopSerializer, WeeklyHoursSerializer


def healthz(request):
    return JsonResponse({'ok': True})


def _error(exc):
    return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _parse_day(value):
    try:
        return date.fromisoformat(value or '')
    except (ValueError, TypeError):
        return None


def _parse_start(value):
    try:
        start = datetime.fromisoformat(value or '')
    except (ValueError, TypeError):
        return None
    if start is None or timezone.is_naive(start):
        return None
    return start


def _guest_booking(code, phone):
    """Guest access to one booking requires knowing both its code and phone."""
    try:
        normalized = phone_number(phone or '')
    except RuleError:
        return None
    return Booking.objects.filter(code=(code or '').strip().upper(), phone=normalized).first()


class ServiceList(APIView):
    def get(self, request):
        return Response(ServiceSerializer(Service.objects.filter(active=True), many=True).data)


class ShopDetail(APIView):
    def get(self, request):
        shop, _ = Shop.objects.get_or_create(pk=1)
        return Response(ShopSerializer(shop).data)


class ScheduleList(APIView):
    """Public: which of the next days are open, matching what the booking page shows."""

    def get(self, request):
        today = timezone.localdate()
        days = int(request.GET.get('days', '3') or 3)
        days = min(max(days, 1), 14)
        # Effective availability per date: dated override wins, else weekly template.
        rows = []
        for i in range(days):
            d = today + timedelta(days=i)
            s = effective_schedule(d)
            if s:
                rows.append({'day': d.isoformat(), 'opens': s.opens.strftime('%H:%M:%S'),
                             'closes': s.closes.strftime('%H:%M:%S'), 'closed': s.closed})
        return Response(rows)


class Availability(APIView):
    def get(self, request):
        day = _parse_day(request.GET.get('day'))
        service = None
        raw = request.GET.get('service', '')
        if raw.isdigit() and len(raw) < 15:
            service = Service.objects.filter(pk=int(raw), active=True).first()
        if not day or not service:
            return Response({'slots': []})
        slots = available(service, day)
        return Response({'slots': [s.isoformat() for s in slots]})


class BookingCreate(APIView):
    def post(self, request):
        service = None
        raw = str(request.data.get('service', ''))
        if raw.isdigit() and len(raw) < 15:
            service = Service.objects.filter(pk=int(raw), active=True).first()
        start = _parse_start(request.data.get('start'))
        if not service or not start:
            return Response({'error': 'اختار الخدمة واليوم والميعاد من جديد.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booking = reserve(service=service, start=start, name=str(request.data.get('name', '')), phone=str(request.data.get('phone', '')))
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingLookup(APIView):
    """Guest finds their booking with code + phone. Limited per web session,
    same 10 attempts / 15 minute lockout policy as the monolith."""

    LOCK_AFTER = 10
    LOCK_MINUTES = 15

    def post(self, request):
        client_key = str(request.data.get('client_key', ''))[:60] or 'unknown'
        with transaction.atomic():
            guard, _ = LookupGuard.objects.get_or_create(key='lookup:' + client_key)
            guard = LookupGuard.objects.select_for_update().get(pk=guard.pk)
            if guard.locked_until and guard.locked_until > timezone.now():
                return _error(RuleError('محاولات كتير. جرّب بعد شوية.'))
            if guard.locked_until:
                guard.failures = 0
                guard.locked_until = None
            booking = _guest_booking(request.data.get('code'), request.data.get('phone'))
            if booking:
                guard.failures = 0
                guard.locked_until = None
                guard.save()
                return Response(BookingSerializer(booking).data)
            guard.failures += 1
            if guard.failures >= self.LOCK_AFTER:
                guard.locked_until = timezone.now() + timedelta(minutes=self.LOCK_MINUTES)
                guard.failures = 0
            guard.save()
        return Response({'error': 'ملقيناش حجز بالبيانات دي.'}, status=status.HTTP_404_NOT_FOUND)


class GuestBookingAvailability(APIView):
    def post(self, request, code):
        booking = _guest_booking(code, request.data.get('phone'))
        if not booking:
            return Response({'error': 'ملقيناش حجز بالبيانات دي.'}, status=status.HTTP_404_NOT_FOUND)
        day = _parse_day(request.data.get('day'))
        if not day:
            return Response({'slots': []})
        service = booking.service
        service.duration = booking.duration
        slots = available(service, day, exclude=booking)
        return Response({'slots': [s.isoformat() for s in slots]})


class GuestBookingChange(APIView):
    def post(self, request, code):
        booking = _guest_booking(code, request.data.get('phone'))
        if not booking:
            return Response({'error': 'ملقيناش حجز بالبيانات دي.'}, status=status.HTTP_404_NOT_FOUND)
        start = _parse_start(request.data.get('start'))
        if not start:
            return Response({'error': 'اختار الخدمة واليوم والميعاد من جديد.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booking = reserve(service=booking.service, start=start, name=booking.name, phone=booking.phone, booking=booking)
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data)


class GuestBookingCancel(APIView):
    def post(self, request, code):
        booking = _guest_booking(code, request.data.get('phone'))
        if not booking:
            return Response({'error': 'ملقيناش حجز بالبيانات دي.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            set_status(booking, 'cancelled')
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data)


class OwnerView(APIView):
    permission_classes = [IsOwnerToken]


class OwnerBookingList(OwnerView):
    def get(self, request):
        selected = request.GET.get('view', 'today')
        qs = Booking.objects.select_related('service')
        if selected != 'all':
            qs = qs.filter(start__date=timezone.localdate() + timedelta(days=1 if selected == 'tomorrow' else 0))
        return Response(BookingSerializer(qs, many=True).data)

    def post(self, request):
        service = None
        raw = str(request.data.get('service', ''))
        if raw.isdigit() and len(raw) < 15:
            service = Service.objects.filter(pk=int(raw), active=True).first()
        start = _parse_start(request.data.get('start'))
        if not service or not start:
            return Response({'error': 'اختار الخدمة واليوم والميعاد من جديد.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booking = reserve(service=service, start=start, name=str(request.data.get('name', '')), phone=str(request.data.get('phone', '')), owner=True)
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class OwnerBookingDetail(OwnerView):
    def get(self, request, pk):
        return Response(BookingSerializer(get_object_or_404(Booking, pk=pk)).data)


class OwnerBookingChange(OwnerView):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        start = _parse_start(request.data.get('start'))
        if not start:
            return Response({'error': 'اختار الخدمة واليوم والميعاد من جديد.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booking = reserve(service=booking.service, start=start, name=booking.name, phone=booking.phone, booking=booking, owner=True)
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data)


class OwnerBookingStatus(OwnerView):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        try:
            set_status(booking, str(request.data.get('status', '')), owner=True)
        except RuleError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data)


class OwnerBookingAvailability(OwnerView):
    def get(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        day = _parse_day(request.GET.get('day'))
        if not day:
            return Response({'slots': []})
        service = booking.service
        service.duration = booking.duration
        slots = available(service, day, exclude=booking)
        return Response({'slots': [s.isoformat() for s in slots]})


class OwnerScheduleList(OwnerView):
    def get(self, request):
        schedules = Schedule.objects.filter(day__gte=timezone.localdate())[:30]
        return Response(ScheduleSerializer(schedules, many=True).data)

    def post(self, request):
        day = _parse_day(request.data.get('day'))
        try:
            opens = time.fromisoformat(str(request.data.get('opens', '')))
            closes = time.fromisoformat(str(request.data.get('closes', '')))
        except (ValueError, TypeError):
            return Response({'error': 'حدد الساعات بالدقيقة من غير ثواني.'}, status=status.HTTP_400_BAD_REQUEST)
        if not day:
            return Response({'error': 'اختار اليوم.'}, status=status.HTTP_400_BAD_REQUEST)
        closed = bool(request.data.get('closed'))
        try:
            schedule = save_schedule(day, opens, closes, closed)
        except RuleError as exc:
            return _error(exc)
        return Response(ScheduleSerializer(schedule).data)


class OwnerWeekly(OwnerView):
    """Recurring weekly template. Per-date Schedule rows always take priority."""

    def get(self, request):
        return Response(WeeklyHoursSerializer(WeeklyHours.objects.all(), many=True).data)

    def post(self, request):
        rows = []
        seen = set()
        for raw in request.data.get('days', []):
            try:
                weekday = int(raw.get('weekday'))
                opens = time.fromisoformat(str(raw.get('opens', '')))
                closes = time.fromisoformat(str(raw.get('closes', '')))
            except (ValueError, TypeError, AttributeError):
                return Response({'error': 'حدد الساعات بالدقيقة من غير ثواني.'}, status=status.HTTP_400_BAD_REQUEST)
            if weekday < 0 or weekday > 6 or weekday in seen:
                return Response({'error': 'أيام الأسبوع مش مظبوطة.'}, status=status.HTTP_400_BAD_REQUEST)
            seen.add(weekday)
            rows.append({'weekday': weekday, 'opens': opens, 'closes': closes, 'closed': bool(raw.get('closed'))})
        if len(rows) != 7:
            return Response({'error': 'احفظ أيام الأسبوع السبعة مع بعض.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            save_weekly(rows)
        except RuleError as exc:
            return _error(exc)
        return Response(WeeklyHoursSerializer(WeeklyHours.objects.all(), many=True).data)


class OwnerServiceList(OwnerView):
    def get(self, request):
        return Response(ServiceSerializer(Service.objects.all(), many=True).data)

    def post(self, request):
        serializer = ServiceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'راجع بيانات الخدمة.', 'fields': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OwnerServiceDetail(OwnerView):
    def patch(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        serializer = ServiceSerializer(service, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'error': 'راجع بيانات الخدمة.', 'fields': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class OwnerBlockList(OwnerView):
    def get(self, request):
        blocks = Block.objects.filter(end__gte=timezone.now()).order_by('start')
        return Response(BlockSerializer(blocks, many=True).data)

    def post(self, request):
        day = _parse_day(request.data.get('day'))
        try:
            start_t = time.fromisoformat(str(request.data.get('start', '')))
            end_t = time.fromisoformat(str(request.data.get('end', '')))
        except (ValueError, TypeError):
            return Response({'error': 'حدد الفترة بالدقيقة من غير ثواني.'}, status=status.HTTP_400_BAD_REQUEST)
        if not day:
            return Response({'error': 'اختار اليوم.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            block = add_block(day, local_dt(day, start_t), local_dt(day, end_t))
        except RuleError as exc:
            return _error(exc)
        return Response(BlockSerializer(block).data, status=status.HTTP_201_CREATED)


class OwnerBlockRemove(OwnerView):
    def post(self, request, pk):
        get_object_or_404(Block, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerShopUpdate(OwnerView):
    def patch(self, request):
        shop, _ = Shop.objects.get_or_create(pk=1)
        serializer = ShopSerializer(shop, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'error': 'راجع بيانات المحل.', 'fields': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)
