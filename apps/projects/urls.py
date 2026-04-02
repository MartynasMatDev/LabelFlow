from django.urls import path
from . import views

urlpatterns = [
    path('',                                         views.dashboard,          name='dashboard'),
    path('projects/',                                views.project_list,       name='project_list'),
    path('projects/create/',                         views.project_create,     name='project_create'),
    path('projects/<int:project_id>/',               views.project_detail,     name='project_detail'),
    path('projects/<int:project_id>/team/',          views.team_management,    name='team_management'),
    path('projects/archived/',                       views.archived_projects,  name='archived_projects'),
    path('projects/<int:project_id>/archive/',       views.archive_project,    name='archive_project'),
    path('projects/<int:project_id>/restore/',       views.restore_project,    name='restore_project'),
    path('projects/<int:project_id>/activity/',      views.activity_feed_json, name='activity_feed_json'),


]