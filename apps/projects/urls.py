from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.dashboard,         name='dashboard'),
    path('projects/create/',               views.project_create,    name='project_create'),
    path('projects/<int:project_id>/',     views.project_detail,    name='project_detail'),
]
