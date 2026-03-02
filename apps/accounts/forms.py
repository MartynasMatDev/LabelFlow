from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True, label='Name')
    last_name = forms.CharField(max_length=50, required=True, label='Last name')
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('Email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email already exists .')
        return email