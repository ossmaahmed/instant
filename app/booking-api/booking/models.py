import secrets
from django.db import models
from django.db.models import Q, F


def booking_code():
    return secrets.token_hex(12).upper()


class Shop(models.Model):
    name = models.CharField(max_length=100, default='مقص | محل تجريبي')
    address = models.CharField(max_length=200, default='العنوان لسه هيتحدد')


class Service(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration = models.PositiveIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name='positive_price'),
            models.CheckConstraint(condition=Q(duration__gte=15) & Q(duration__lte=480), name='valid_duration'),
        ]


class Schedule(models.Model):
    day = models.DateField(unique=True)
    closed = models.BooleanField(default=False)
    opens = models.TimeField(default='10:00')
    closes = models.TimeField(default='22:00')

    class Meta:
        ordering = ['day']
        constraints = [models.CheckConstraint(condition=Q(closed=True) | Q(closes__gt=F('opens')), name='valid_hours')]


class WeeklyHours(models.Model):
    """Recurring weekly template. A per-date Schedule row always wins over it;
    dates with neither stay unbookable."""
    weekday = models.PositiveSmallIntegerField(unique=True)  # Monday=0 .. Sunday=6
    closed = models.BooleanField(default=False)
    opens = models.TimeField(default='10:00')
    closes = models.TimeField(default='22:00')

    class Meta:
        ordering = ['weekday']
        constraints = [models.CheckConstraint(condition=Q(closed=True) | Q(closes__gt=F('opens')), name='valid_weekly_hours')]


class Booking(models.Model):
    CONFIRMED = 'confirmed'
    STATES = [('confirmed', 'مؤكد'), ('completed', 'تمت الزيارة'), ('no_show', 'لم يحضر'), ('cancelled', 'ملغي')]
    code = models.CharField(max_length=24, unique=True, default=booking_code, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=11)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    service_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration = models.PositiveIntegerField()
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATES, default='confirmed')
    source = models.CharField(max_length=10, default='customer')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start']
        constraints = [models.CheckConstraint(condition=Q(end__gt=F('start')), name='positive_booking_length')]


class Block(models.Model):
    day = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    start = models.DateTimeField()
    end = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end__gt=F('start')), name='positive_block_length')]


class Occupancy(models.Model):
    # One row per occupied minute, independent of grid or service duration.
    minute = models.DateTimeField(unique=True)
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.CASCADE)
    block = models.ForeignKey(Block, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(booking__isnull=False) & Q(block__isnull=True)) | (Q(booking__isnull=True) & Q(block__isnull=False)), name='one_occupancy_owner')]


class LookupGuard(models.Model):
    # Rate limiter for guest booking lookups (code + phone), keyed by the
    # caller's web session. Separate from the owner login guard, which lives
    # in the identity service.
    key = models.CharField(max_length=70, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
