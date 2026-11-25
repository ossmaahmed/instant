from django import template

from pages.timefmt import arabic_time

register = template.Library()


@register.filter(name='ar_time')
def ar_time(value):
    return arabic_time(value)
