from datetime import date, datetime, time, timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .timefmt import arabic_time
from . import api
from .forms import BlockForm, GuestForm, HoursForm, LookupForm, PasswordForm, ServiceForm, ShopForm


def _dt(value):
    try:
        parsed = datetime.fromisoformat(value or '')
        return None if timezone.is_naive(parsed) else parsed
    except (ValueError, TypeError):
        return None


def _day(value):
    try:
        return date.fromisoformat(value or '')
    except (ValueError, TypeError):
        return None


def _time(value):
    try:
        return time.fromisoformat(value or '')
    except (ValueError, TypeError):
        return None


def _booking(raw):
    raw = dict(raw)
    raw['start'] = _dt(raw.get('start'))
    raw['end'] = _dt(raw.get('end'))
    return raw


def _schedule_obj(raw):
    return {'day': _day(raw.get('day')), 'closed': raw.get('closed'), 'opens': _time(raw.get('opens')), 'closes': _time(raw.get('closes'))}


def _editable(booking):
    return booking['status'] == 'confirmed' and booking['start'] - timezone.now() >= timedelta(minutes=settings.CUSTOMER_CUTOFF_MINUTES)


def home(request):
    try:
        services = api.services()
        days = [_schedule_obj(s) for s in api.schedules(3)]
    except api.ApiError as e:
        messages.error(request, str(e))
        services, days = [], []
    return render(request, 'booking/home.html', {'services': services, 'days': days})


def _selection(request, token=None, booking=None):
    """Resolve service/day/slots/selected start from the request, using the
    booking service for availability. For an existing booking the availability
    call excludes the booking's own current minutes."""
    data = request.POST if request.method == 'POST' else request.GET
    service = None
    raw = str(data.get('service', ''))
    if booking:
        service = {'pk': 'current'}
    elif raw.isdigit() and len(raw) < 15:
        try:
            service = next((s for s in api.services() if s['pk'] == int(raw)), None)
        except api.ApiError as e:
            messages.error(request, str(e))
    day = _day(data.get('day'))
    slots = []
    if service and day:
        try:
            if booking and token:
                slots = api.owner_availability(token, booking['pk'], day.isoformat())
            elif booking:
                slots = api.guest_availability(booking['code'], booking['phone'], day.isoformat())
            else:
                slots = api.availability(day.isoformat(), service['pk'])
            slots = [_dt(s) for s in slots]
        except api.ApiError as e:
            messages.error(request, str(e))
    selected = _dt(data.get('start'))
    return service, day, slots, selected


def _day_options():
    days = [timezone.localdate() + timedelta(days=i) for i in range(3)]
    try:
        schedules = {s['day']: s for s in (_schedule_obj(x) for x in api.schedules(3))}
    except api.ApiError:
        schedules = {}
    return [{'day': d, 'schedule': schedules.get(d), 'off': d not in schedules or schedules[d]['closed']} for d in days]


def _booking_page(request, booking=None, token=None, owner=False):
    service, day, slots, start = _selection(request, token=token, booking=booking)
    form = GuestForm(request.POST or None, initial={'name': booking['name'], 'phone': booking['phone']} if booking else None)
    if request.method == 'POST' and form.is_valid():
        if not service or not day or not start or timezone.localtime(start).date() != day:
            form.add_error(None, 'اختار الخدمة واليوم والميعاد من جديد.')
        else:
            try:
                if owner and booking:
                    saved = api.owner_change_booking(token, booking['pk'], start.isoformat())
                elif owner:
                    saved = api.owner_create_booking(token, service['pk'], start.isoformat(), **form.cleaned_data)
                elif booking:
                    saved = api.guest_change(booking['code'], booking['phone'], start.isoformat())
                else:
                    saved = api.create_booking(service['pk'], start.isoformat(), **form.cleaned_data)
                saved = _booking(saved)
                if owner:
                    messages.success(request, 'الحجز اتسجل واتحفظ.')
                    return redirect('owner_booking', pk=saved['pk'])
                request.session['booking_code'] = saved['code']
                request.session['booking_phone'] = saved['phone']
                request.session['booking_data'] = {**saved, 'start': saved['start'].isoformat(), 'end': saved['end'].isoformat()}
                return redirect('manage_detail')
            except api.ApiError as e:
                form.add_error(None, str(e))
    try:
        services = api.services()
    except api.ApiError:
        services = []
    return render(request, 'booking/book.html', {
        'services': services, 'selected_service': service, 'selected_day': day, 'slots': slots,
        'selected_start': start, 'form': form, 'day_options': _day_options(),
        'editing': booking, 'owner_mode': owner,
        'layout': 'booking/owner_base.html' if owner else 'booking/base.html',
    })


def book(request):
    return _booking_page(request)


@never_cache
def manage_lookup(request):
    form = LookupForm(request.POST or None)
    if not request.session.session_key:
        request.session.create()
    if request.method == 'POST' and form.is_valid():
        try:
            saved = api.lookup(form.cleaned_data['code'], form.cleaned_data['phone'], request.session.session_key)
            saved = _booking(saved)
            request.session.cycle_key()
            request.session['booking_code'] = saved['code']
            request.session['booking_phone'] = saved['phone']
            request.session['booking_data'] = {**saved, 'start': saved['start'].isoformat(), 'end': saved['end'].isoformat()}
            return redirect('manage_detail')
        except api.ApiError as e:
            form.add_error(None, str(e))
    return render(request, 'booking/form.html', {'form': form, 'title': 'إدارة حجزك', 'intro': 'اكتب الكود ورقم الموبايل اللي حجزت بيه.', 'button': 'عرض الحجز'})


def _session_booking(request):
    data = request.session.get('booking_data')
    if not data or data.get('code') != request.session.get('booking_code'):
        return None
    return _booking(data)


def _store_booking(request, saved):
    saved = _booking(saved)
    request.session['booking_data'] = {**saved, 'start': saved['start'].isoformat(), 'end': saved['end'].isoformat()}
    return saved


@never_cache
def manage_detail(request):
    booking = _session_booking(request)
    if not booking:
        return redirect('manage')
    return render(request, 'booking/detail.html', {'b': booking, 'editable': _editable(booking)})


@never_cache
def manage_change(request):
    booking = _session_booking(request)
    if not booking:
        return redirect('manage')
    if not _editable(booking):
        messages.error(request, 'وقت التعديل والإلغاء خلص حسب القاعدة التجريبية الحالية. تواصل مع صاحب المحل.')
        return redirect('manage_detail')
    return _booking_page(request, booking=booking)


@require_POST
def manage_cancel(request):
    booking = _session_booking(request)
    if not booking:
        return redirect('manage')
    if request.POST.get('confirm') != 'yes':
        messages.error(request, 'أكد الإلغاء الأول.')
        return redirect('manage_detail')
    try:
        _store_booking(request, api.guest_cancel(booking['code'], booking['phone']))
        messages.success(request, 'الحجز اتلغى والميعاد بقى متاح.')
    except api.ApiError as e:
        messages.error(request, str(e))
    return redirect('manage_detail')


def owner_required(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        token = request.session.get('owner_token')
        if not token:
            return redirect('owner_login')
        try:
            return view(request, token, *args, **kwargs)
        except api.Unauthorized:
            request.session.pop('owner_token', None)
            messages.error(request, 'انتهت الجلسة. سجّل دخولك تاني.')
            return redirect('owner_login')
        except api.ApiError as e:
            # Never redirect to 'dashboard' here: dashboard itself lands in this
            # branch when a backing API is down, which made an infinite
            # redirect loop. Show a retry-later page instead.
            return render(request, 'booking/error.html', {'error': str(e)}, status=503)
    return wrapped


@never_cache
def owner_login(request):
    if request.session.get('owner_token'):
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        try:
            result = api.login(request.POST.get('username', '')[:150], request.POST.get('password', ''))
            request.session.cycle_key()
            request.session['owner_token'] = result['token']
            return redirect('dashboard')
        except api.ApiError as e:
            error = str(e)
    return render(request, 'booking/login.html', {'error': error})


@require_POST
def owner_logout(request):
    token = request.session.get('owner_token')
    if token:
        try:
            api.logout(token)
        except api.ApiError:
            pass
    request.session.flush()
    return redirect('home')


@owner_required
def dashboard(request, token):
    selected = request.GET.get('view', 'today')
    items = [_booking(b) for b in api.owner_bookings(token, selected)]
    if request.GET.get('format') == 'json':
        return JsonResponse({'bookings': [{
            'id': b['pk'], 'name': b['name'], 'phone': b['phone'], 'service': b['service_name'],
            'time': timezone.localtime(b['start']).strftime('%Y/%m/%d') + ' · ' + arabic_time(timezone.localtime(b['start'])), 'status': b['get_status_display'],
        } for b in items]})
    return render(request, 'booking/dashboard.html', {'bookings': items, 'view': selected})


@owner_required
def owner_booking(request, token, pk):
    booking = _booking(api.owner_booking(token, pk))
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            messages.error(request, 'أكد التغيير الأول.')
        else:
            try:
                api.owner_set_status(token, pk, request.POST.get('status'))
                messages.success(request, 'حالة الحجز اتحدثت.')
            except api.ApiError as e:
                messages.error(request, str(e))
        return redirect('owner_booking', pk=pk)
    return render(request, 'booking/detail.html', {'b': booking, 'owner_mode': True, 'editable': booking['status'] == 'confirmed', 'layout': 'booking/owner_base.html'})


@owner_required
def owner_manual(request, token):
    return _booking_page(request, token=token, owner=True)


@owner_required
def owner_change(request, token, pk):
    booking = _booking(api.owner_booking(token, pk))
    return _booking_page(request, booking=booking, token=token, owner=True)


AR_WEEKDAYS = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']  # Monday=0 .. Sunday=6
WEEK_DISPLAY_ORDER = [5, 6, 0, 1, 2, 3, 4]  # Saturday first


@owner_required
def hours(request, token):
    if request.method == 'POST' and 'weekly_save' in request.POST:
        days = []
        for i in range(7):
            days.append({
                'weekday': i,
                'opens': request.POST.get(f'opens-{i}', ''),
                'closes': request.POST.get(f'closes-{i}', ''),
                'closed': bool(request.POST.get(f'closed-{i}')),
            })
        try:
            api.owner_save_weekly(token, days)
            messages.success(request, 'الجدول الأسبوعي اتحفظ. الأيام الجديدة هتفتح للحجز تلقائيًا حسب الجدول ده.')
            return redirect('hours')
        except api.ApiError as e:
            messages.error(request, str(e))
    form = HoursForm(None if (request.method == 'POST' and 'weekly_save' in request.POST) else (request.POST or None), initial={'day': timezone.localdate()})
    if request.method == 'POST' and 'weekly_save' not in request.POST and form.is_valid():
        d = form.cleaned_data
        try:
            api.owner_save_schedule(token, d['day'].isoformat(), d['opens'].strftime('%H:%M'), d['closes'].strftime('%H:%M'), d['closed'])
            messages.success(request, 'ساعات اليوم اتحدثت وهتظهر للزبون تلقائيًا.')
            return redirect('hours')
        except api.ApiError as e:
            form.add_error(None, str(e))
    schedules = [_schedule_obj(s) for s in api.owner_schedules(token)]
    saved_weekly = {w['weekday']: w for w in api.owner_weekly(token)}
    weekly = []
    for i in WEEK_DISPLAY_ORDER:
        w = saved_weekly.get(i, {})
        weekly.append({'weekday': i, 'name': AR_WEEKDAYS[i],
                       'opens': (w.get('opens') or '10:00')[:5], 'closes': (w.get('closes') or '22:00')[:5],
                       'closed': w.get('closed', False), 'saved': bool(w)})
    return render(request, 'booking/hours.html', {'form': form, 'schedules': schedules, 'weekly': weekly})


@owner_required
def services(request, token, pk=None):
    all_services = api.owner_services(token)
    editing = next((s for s in all_services if pk and s['pk'] == pk), None)
    form = ServiceForm(request.POST or None, initial=editing)
    if request.method == 'POST' and form.is_valid():
        try:
            api.owner_save_service(token, form.cleaned_data, pk=pk if editing else None)
            messages.success(request, 'الخدمة اتحفظت. الحجوزات القديمة محتفظة بسعرها ومدتها.')
            return redirect('services')
        except api.ApiError as e:
            form.add_error(None, str(e))
    return render(request, 'booking/services.html', {'form': form, 'services': all_services, 'editing_service': editing})


@owner_required
def blocks(request, token):
    form = BlockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            api.owner_add_block(token, d['day'].isoformat(), d['start'].strftime('%H:%M'), d['end'].strftime('%H:%M'))
            messages.success(request, 'الفترة اتقفلت.')
            return redirect('blocks')
        except api.ApiError as e:
            form.add_error(None, str(e))
    raw_blocks = api.owner_blocks(token)
    for b in raw_blocks:
        b['start'] = _dt(b.get('start'))
        b['end'] = _dt(b.get('end'))
    return render(request, 'booking/blocks.html', {'form': form, 'blocks': raw_blocks})


@owner_required
@require_POST
def unblock(request, token, pk):
    if request.POST.get('confirm') == 'yes':
        try:
            api.owner_remove_block(token, pk)
            messages.success(request, 'الفترة بقت متاحة.')
        except api.ApiError as e:
            messages.error(request, str(e))
    return redirect('blocks')


@owner_required
def shop_settings(request, token):
    shop = api.shop()
    form = ShopForm(request.POST or None, initial=shop)
    if request.method == 'POST' and form.is_valid():
        try:
            api.owner_update_shop(token, form.cleaned_data)
            messages.success(request, 'بيانات المحل اتحفظت.')
            return redirect('settings')
        except api.ApiError as e:
            form.add_error(None, str(e))
    return render(request, 'booking/form.html', {'form': form, 'title': 'بيانات المحل', 'button': 'حفظ البيانات', 'layout': 'booking/owner_base.html'})


@owner_required
def password_change(request, token):
    form = PasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            api.change_password(token, form.cleaned_data['old_password'], form.cleaned_data['new_password'])
            messages.success(request, 'كلمة السر اتغيرت.')
            return redirect('dashboard')
        except api.ApiError as e:
            form.add_error(None, str(e))
    return render(request, 'booking/form.html', {'form': form, 'title': 'تغيير كلمة السر', 'button': 'تغيير كلمة السر', 'layout': 'booking/owner_base.html'})
