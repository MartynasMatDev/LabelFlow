from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.dashboard,         name='dashboard'),
    path('projects/',                      views.project_list,      name='project_list'),
    path('projects/create/',               views.project_create,    name='project_create'),
    path('projects/<int:project_id>/',     views.project_detail,    name='project_detail'),
    path('projects/<int:project_id>/team/', views.team_management,  name='team_management'),
]
