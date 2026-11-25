from datetime import time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from booking.models import Schedule, Service, Shop, WeeklyHours


class Command(BaseCommand):
    help = 'Create fictional shop data and a rolling weekly demo template. Never creates owner credentials.'

    def handle(self, *args, **kwargs):
        if not settings.SEED_DEMO:
            raise CommandError('Demo seed is disabled (SEED_DEMO=false).')
        Shop.objects.get_or_create(pk=1)
        for name, price, duration in [('قص شعر', 120, 30), ('تهذيب دقن', 70, 30), ('شعر ودقن', 180, 60)]:
            Service.objects.get_or_create(name=name, defaults={'price': price, 'duration': duration})
        if not Schedule.objects.exists() and not WeeklyHours.objects.exists():
            # Fresh demo install only: a rolling weekly template so availability
            # follows the calendar. Existing installs keep their own data.
            for weekday in range(7):
                WeeklyHours.objects.get_or_create(weekday=weekday, defaults={'opens': time(10), 'closes': time(22)})
        self.stdout.write(self.style.SUCCESS('Fictional services and hours ready. No account was created.'))
