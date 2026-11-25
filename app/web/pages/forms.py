from django import forms

from .phone import PhoneError, phone_number


class GuestForm(forms.Form):
    name = forms.CharField(label='اسمك', min_length=2, max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    phone = forms.CharField(label='رقم الموبايل', max_length=25, widget=forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'tel', 'dir': 'ltr', 'placeholder': '01xxxxxxxxx'}))

    def clean_phone(self):
        try:
            return phone_number(self.cleaned_data['phone'])
        except PhoneError as e:
            raise forms.ValidationError(str(e))


class LookupForm(forms.Form):
    code = forms.CharField(label='كود الحجز', max_length=24, widget=forms.TextInput(attrs={'dir': 'ltr', 'autocomplete': 'off'}))
    phone = forms.CharField(label='رقم الموبايل', max_length=25, widget=forms.TextInput(attrs={'dir': 'ltr', 'inputmode': 'tel'}))

    def clean_phone(self):
        try:
            return phone_number(self.cleaned_data['phone'])
        except PhoneError as e:
            raise forms.ValidationError(str(e))


class HoursForm(forms.Form):
    day = forms.DateField(label='اليوم', widget=forms.DateInput(attrs={'type': 'date'}))
    opens = forms.TimeField(label='بداية الشغل', widget=forms.TimeInput(attrs={'type': 'time'}), initial='10:00')
    closes = forms.TimeField(label='نهاية الشغل', widget=forms.TimeInput(attrs={'type': 'time'}), initial='22:00')
    closed = forms.BooleanField(label='اليوم إجازة', required=False)


class ServiceForm(forms.Form):
    name = forms.CharField(label='اسم الخدمة', max_length=100)
    price = forms.DecimalField(label='السعر بالجنيه', max_digits=8, decimal_places=2)
    duration = forms.IntegerField(label='المدة بالدقايق')
    active = forms.BooleanField(label='متاحة للحجز', required=False, initial=True)

    def clean_duration(self):
        d = self.cleaned_data['duration']
        if not 15 <= d <= 480:
            raise forms.ValidationError('المدة من ١٥ لـ ٤٨٠ دقيقة.')
        return d

    def clean_price(self):
        p = self.cleaned_data['price']
        if p <= 0:
            raise forms.ValidationError('السعر لازم يكون أكبر من صفر.')
        return p


class ShopForm(forms.Form):
    name = forms.CharField(label='اسم المحل', max_length=100)
    address = forms.CharField(label='عنوان المحل', max_length=200)


class BlockForm(forms.Form):
    day = forms.DateField(label='اليوم', widget=forms.DateInput(attrs={'type': 'date'}))
    start = forms.TimeField(label='من', widget=forms.TimeInput(attrs={'type': 'time'}))
    end = forms.TimeField(label='لحد', widget=forms.TimeInput(attrs={'type': 'time'}))


class PasswordForm(forms.Form):
    old_password = forms.CharField(label='كلمة السر الحالية', widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    new_password = forms.CharField(label='كلمة السر الجديدة', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    new_password2 = forms.CharField(label='تأكيد كلمة السر الجديدة', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') and cleaned.get('new_password') != cleaned.get('new_password2'):
            self.add_error('new_password2', 'كلمتا السر الجديدتين مش متطابقتين.')
        return cleaned
