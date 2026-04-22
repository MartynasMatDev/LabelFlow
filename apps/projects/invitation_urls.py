# apps/projects/invitation_urls.py
from django.urls import path
from . import views
from . import workspace_views

urlpatterns = [
    # Project invitations
    path('<uuid:token>/',         views.invitation_prompt,  name='invitation_prompt'),
    path('<uuid:token>/accept/',  views.accept_invitation,  name='accept_invitation'),

    # Workspace invitations
    path('workspace/<uuid:token>/',        workspace_views.workspace_invitation_prompt,  name='workspace_invitation_prompt'),
    path('workspace/<uuid:token>/accept/', workspace_views.accept_workspace_invitation,  name='accept_workspace_invitation'),
]
