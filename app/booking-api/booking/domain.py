import re
from datetime import datetime, timedelta
from django.conf import settings
from django.db import transaction, IntegrityError, OperationalError
from django.utils import timezone
from .models import Schedule, WeeklyHours, Booking, Occupancy, Block

class RuleError(Exception): pass

def phone_number(value):
    value=value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789'))
    value=re.sub(r'[\s()-]','',value)
    if value.startswith('+20'): value='0'+value[3:]
    if not re.fullmatch(r'01[0125]\d{8}',value): raise RuleError('اكتب رقم موبايل مصري صحيح من ١١ رقم.')
    return value

def local_dt(day,t): return timezone.make_aware(datetime.combine(day,t))
def minutes(start,end):
    while start < end:
        yield start
        start += timedelta(minutes=1)

def validate_day(day):
    today=timezone.localdate()
    if not today <= day <= today+timedelta(days=2): raise RuleError('الحجز متاح من النهارده لحد يومين قدام بس.')

def validate_slot(schedule,start,duration):
    validate_day(timezone.localtime(start).date())
    end=start+timedelta(minutes=duration)
    local=timezone.localtime(start)
    if schedule.closed or start < local_dt(schedule.day,schedule.opens) or end > local_dt(schedule.day,schedule.closes):
        raise RuleError('الميعاد ده خارج ساعات الشغل أو اليوم إجازة.')
    if start <= timezone.now(): raise RuleError('الميعاد فات. اختار ميعاد جاي.')
    offset=int((start-local_dt(schedule.day,schedule.opens)).total_seconds()//60)
    if local.second or local.microsecond or offset % settings.SLOT_STEP_MINUTES: raise RuleError('اختار ميعاد من المواعيد المعروضة.')
    return end

class _Effective:
    """Dated override if one exists, else the weekly template for that weekday."""
    def __init__(self, day, opens, closes, closed, source):
        self.day, self.opens, self.closes, self.closed, self.source = day, opens, closes, closed, source


def effective_schedule(day):
    s = Schedule.objects.filter(day=day).first()
    if s: return s
    w = WeeklyHours.objects.filter(weekday=day.weekday()).first()
    if w: return _Effective(day, w.opens, w.closes, w.closed, 'weekly')
    return None


def save_weekly(rows):
    """Save the whole weekly template atomically. rows: list of dicts with
    weekday/opens/closes/closed. Refuses changes that would cut off existing
    bookings on dates the template governs (dated overrides are left alone)."""
    today = timezone.localdate()
    with transaction.atomic():
        for row in rows:
            weekday, opens, closes, closed = row['weekday'], row['opens'], row['closes'], row['closed']
            if opens.second or closes.second: raise RuleError('حدد الساعات بالدقيقة من غير ثواني.')
            if not closed and closes <= opens: raise RuleError('نهاية الشغل لازم تكون بعد البداية في نفس اليوم.')
            for i in range(3):
                d = today + timedelta(days=i)
                if d.weekday() != weekday or Schedule.objects.filter(day=d).exists(): continue
                bookings = Booking.objects.filter(start__date=d).exclude(status='cancelled')
                if bookings.exists() and (closed or bookings.filter(start__lt=local_dt(d,opens)).exists() or bookings.filter(end__gt=local_dt(d,closes)).exists()):
                    raise RuleError('فيه حجوزات موجودة هتتعارض مع الجدول الجديد. دير الحجوزات المتعارضة الأول.')
        for row in rows:
            w,_ = WeeklyHours.objects.select_for_update().get_or_create(weekday=row['weekday'])
            w.opens, w.closes, w.closed = row['opens'], row['closes'], row['closed']
            w.save()
    return WeeklyHours.objects.all()


def available(service,day,exclude=None):
    try: validate_day(day)
    except RuleError: return []
    s=effective_schedule(day)
    if not s or s.closed: return []
    start,end=local_dt(day,s.opens),local_dt(day,s.closes)
    occupied=Occupancy.objects.filter(minute__gte=start,minute__lt=end)
    if exclude: occupied=occupied.exclude(booking=exclude)
    taken=set(occupied.values_list('minute',flat=True))
    slots=[]
    while start+timedelta(minutes=service.duration) <= end:
        finish=start+timedelta(minutes=service.duration)
        if start>timezone.now() and not any(m in taken for m in minutes(start,finish)): slots.append(start)
        start+=timedelta(minutes=settings.SLOT_STEP_MINUTES)
    return slots

def reserve(*,service,start,name,phone,booking=None,owner=False):
    name=name.strip()
    if len(name)<2 or len(name)>100: raise RuleError('الاسم من حرفين لحد ١٠٠ حرف.')
    phone=phone_number(phone)
    try:
        with transaction.atomic():
            day=timezone.localtime(start).date()
            s=Schedule.objects.select_for_update().filter(day=day).first()
            if not s:
                w=WeeklyHours.objects.select_for_update().filter(weekday=day.weekday()).first()
                if w: s=_Effective(day, w.opens, w.closes, w.closed, 'weekly')
            if not s: raise RuleError('صاحب المحل لسه محددش مواعيد اليوم ده.')
            if booking:
                booking=Booking.objects.select_for_update().get(pk=booking.pk)
                can_change(booking,owner)
                # Existing bookings keep their original duration and price.
                duration=booking.duration
            else:
                service=type(service).objects.get(pk=service.pk)
                if not service.active: raise RuleError('الخدمة دي مش متاحة للحجز الجديد.')
                duration=service.duration
            end=validate_slot(s,start,duration)
            if booking: Occupancy.objects.filter(booking=booking).delete()
            else: booking=Booking(service=service,service_name=service.name,price=service.price,duration=duration,source='owner' if owner else 'customer')
            booking.name=name; booking.phone=phone; booking.start=start; booking.end=end
            booking.save()
            Occupancy.objects.bulk_create([Occupancy(minute=m,booking=booking) for m in minutes(start,end)])
            return booking
    except (IntegrityError,OperationalError):
        raise RuleError('الميعاد اتحجز دلوقتي أو حصل تعارض. اختار ميعاد تاني وحاول تاني.')

def can_change(booking,owner=False):
    if booking.status!='confirmed': raise RuleError('الحجز ده مش مؤكد حاليًا ومش قابل للتعديل.')
    if not owner and booking.start-timezone.now() < timedelta(minutes=settings.CUSTOMER_CUTOFF_MINUTES):
        raise RuleError('وقت التعديل والإلغاء خلص حسب القاعدة التجريبية الحالية. تواصل مع صاحب المحل.')

def set_status(booking,status,owner=False):
    if status not in dict(Booking.STATES) or (not owner and status!='cancelled'): raise RuleError('تغيير غير مسموح.')
    with transaction.atomic():
        # Same lock order as reserve and schedule changes; weekly-governed days
        # have no dated row, so lock the weekly row instead.
        _day = timezone.localtime(booking.start).date()
        if not Schedule.objects.select_for_update().filter(day=_day).exists():
            WeeklyHours.objects.select_for_update().filter(weekday=_day.weekday()).first()
        b=Booking.objects.select_for_update().get(pk=booking.pk)
        can_change(b,owner)
        if status in ['completed','no_show'] and b.start>timezone.now(): raise RuleError('مينفعش تسجل زيارة أو عدم حضور قبل الميعاد.')
        b.status=status; b.save(update_fields=['status'])
        if status=='cancelled': Occupancy.objects.filter(booking=b).delete()

def save_schedule(day,opens,closes,closed):
    if opens.second or closes.second or opens.microsecond or closes.microsecond: raise RuleError('حدد الساعات بالدقيقة من غير ثواني.')
    if not closed and closes <= opens: raise RuleError('نهاية الشغل لازم تكون بعد البداية في نفس اليوم.')
    with transaction.atomic():
        s,_=Schedule.objects.get_or_create(day=day)
        s=Schedule.objects.select_for_update().get(pk=s.pk)
        bookings=Booking.objects.filter(start__date=day).exclude(status='cancelled')
        if bookings.exists() and (closed or bookings.filter(start__lt=local_dt(day,opens)).exists() or bookings.filter(end__gt=local_dt(day,closes)).exists()):
            raise RuleError('فيه حجوزات موجودة هتتعارض. التغيير مرفوض في النسخة التجريبية لحد ما تدير الحجوزات بنفسك.')
        s.opens=opens;s.closes=closes;s.closed=closed;s.save()
        return s

def add_block(day,start,end):
    try:
        with transaction.atomic():
            s=Schedule.objects.select_for_update().filter(day=day).first()
            if not s:
                # Blocking part of a weekly-governed day snapshots the template
                # into a dated override, so the block has a row to attach to.
                w=WeeklyHours.objects.filter(weekday=day.weekday()).first()
                if not w or w.closed: raise RuleError('حدد ساعات الشغل لليوم الأول.')
                s=Schedule.objects.create(day=day, opens=w.opens, closes=w.closes, closed=False)
            if start.second or end.second or start.microsecond or end.microsecond: raise RuleError('حدد الفترة بالدقيقة من غير ثواني.')
            if end<=start or start<local_dt(day,s.opens) or end>local_dt(day,s.closes): raise RuleError('الفترة لازم تكون جوه ساعات الشغل ونهايتها بعد بدايتها.')
            b=Block.objects.create(day=s,start=start,end=end)
            Occupancy.objects.bulk_create([Occupancy(minute=m,block=b) for m in minutes(start,end)])
            return b
    except Schedule.DoesNotExist: raise RuleError('حدد ساعات الشغل لليوم الأول.')
    except (IntegrityError,OperationalError): raise RuleError('الفترة دي عليها حجز أو مقفولة بالفعل.')
