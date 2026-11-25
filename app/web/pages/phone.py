import re


class PhoneError(Exception):
    pass


def phone_number(value):
    value = value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    value = re.sub(r'[\s()-]', '', value)
    if value.startswith('+20'):
        value = '0' + value[3:]
    if not re.fullmatch(r'01[0125]\d{8}', value):
        raise PhoneError('اكتب رقم موبايل مصري صحيح من ١١ رقم.')
    return value
