from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, UserCreationForm,
)
from django.contrib.auth.models import User


INPUT_CLASSES = (
    'form-input w-full px-3 py-2 border border-gray-300 rounded-md '
    'focus:outline-none focus:ring-2 focus:ring-blue-500'
)


class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Necesario para recuperar tu cuenta.')

    acepta_terminos = forms.BooleanField(
        required=True,
        label='Acepto los términos y condiciones',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases a todos los inputs
        for field_name in ('username', 'email', 'password1', 'password2'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'class': 'auth-input',
                    'autocomplete': 'off',
                })
        self.fields['acepta_terminos'].widget.attrs.update({
            'class': 'auth-checkbox',
        })

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ese correo ya está registrado.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower().strip()
        if commit:
            user.save()
            user.profile.acepta_terminos = self.cleaned_data['acepta_terminos']
            user.profile.save(update_fields=['acepta_terminos'])
        return user


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'auth-input',
            'autofocus': True,
            'placeholder': 'Tu nombre de usuario',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'auth-input',
            'placeholder': 'Tu contraseña',
        })