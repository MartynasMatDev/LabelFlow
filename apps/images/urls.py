from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.image_list,         name='image_list'),
    path('upload/',                       views.image_upload,       name='image_upload'),
    path('upload/ajax/',                  views.image_upload_ajax,  name='image_upload_ajax'),
    path('project/<int:project_id>/',     views.image_list,         name='project_images'),
    path('<int:image_id>/delete/',        views.image_delete,       name='image_delete'),
    path('<int:pk>/',                     views.image_detail,       name='image_detail'),
    path('batch-tag/',                    views.batch_tag,          name='batch_tag'),
]