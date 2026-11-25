from rest_framework import serializers

from .models import Block, Booking, Schedule, Service, Shop, WeeklyHours


class TrimmedDecimalField(serializers.DecimalField):
    """Writable decimal that serializes without padding zeros (120.00 -> "120")."""

    def to_representation(self, value):
        return format(value.normalize(), 'f')


class ServiceSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(source='id', read_only=True)
    price = TrimmedDecimalField(max_digits=8, decimal_places=2)

    class Meta:
        model = Service
        fields = ['pk', 'name', 'price', 'duration', 'active']


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['name', 'address']


class WeeklyHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyHours
        fields = ['weekday', 'closed', 'opens', 'closes']


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ['day', 'closed', 'opens', 'closes']


class BookingSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(source='id', read_only=True)
    price = TrimmedDecimalField(max_digits=8, decimal_places=2, read_only=True)
    get_status_display = serializers.CharField(read_only=True)

    class Meta:
        model = Booking
        fields = ['pk', 'code', 'name', 'phone', 'service_name', 'price', 'duration', 'start', 'end', 'status', 'get_status_display', 'source']


class BlockSerializer(serializers.ModelSerializer):
    pk = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Block
        fields = ['pk', 'start', 'end']
