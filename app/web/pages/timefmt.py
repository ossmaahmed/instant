"""Arabic 12-hour time rendering shared by templates and view payloads."""
AR_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')

DAYPARTS = ((5, 'ليلًا'), (12, 'صباحًا'), (13, 'ظهرًا'), (17, 'عصرًا'), (24, 'مساءً'))


def arabic_time(value):
    """Render a time/datetime as natural Arabic 12-hour text, e.g. ٢:٠٠ عصرًا."""
    hour, minute = value.hour, value.minute
    daypart = next(label for end, label in DAYPARTS if hour < end)
    hour12 = hour % 12 or 12
    return f'{hour12}:{minute:02d} {daypart}'.translate(AR_DIGITS)
