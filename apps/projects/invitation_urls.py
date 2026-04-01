# apps/projects/invitation_urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:token>/',         views.invitation_prompt,  name='invitation_prompt'),
    path('<uuid:token>/accept/',  views.accept_invitation,  name='accept_invitation'),
]