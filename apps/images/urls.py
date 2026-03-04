from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.image_list,   name='image_list'),
    path('upload/',                       views.image_upload, name='image_upload'),
    path('project/<int:project_id>/',     views.image_list,   name='project_images'),
    path('<int:image_id>/delete/',        views.image_delete, name='image_delete'),
    path('<int:pk>/', views.image_detail, name='image_detail'),

]
