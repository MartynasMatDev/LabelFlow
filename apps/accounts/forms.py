from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True, label='First name')
    last_name = forms.CharField(max_length=50, required=True, label='Last name')
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already registered.')
        return email


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=False, label='First name')
    last_name = forms.CharField(max_length=50, required=False, label='Last name')
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = UserProfile
        fields = (
            'bio',
            'organization',
            'job_title',
            'notify_team_invites',
            'notify_comments',
            'notify_weekly'
        )
        labels = {
            'bio': 'Bio',
            'organization': 'Organization',
            'job_title': 'Job title',
            'notify_team_invites': 'Team invitations',
            'notify_comments': 'Comment notifications',
            'notify_weekly': 'Weekly report',
        }