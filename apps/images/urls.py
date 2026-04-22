from django.urls import path
from . import views

urlpatterns = [
    # Image list / upload
    path('',                              views.image_list,             name='image_list'),
    path('upload/',                       views.image_upload,           name='image_upload'),
    path('upload/ajax/',                  views.image_upload_ajax,      name='image_upload_ajax'),
    path('project/<int:project_id>/',     views.image_list,             name='project_images'),

    # Single image actions
    path('<int:pk>/',                     views.image_detail,           name='image_detail'),
    path('<int:image_id>/delete/',        views.image_delete,           name='image_delete'),

    # Annotation
    path('<int:pk>/annotate/',            views.image_annotate,         name='image_annotate'),
    path('<int:pk>/annotate/save/',       views.annotation_save,        name='annotation_save'),
    path('<int:pk>/annotate/box/<int:box_pk>/delete/', views.annotation_delete_box, name='annotation_delete_box'),
    path('<int:pk>/annotate/polygon/<int:poly_pk>/delete/', views.polygon_delete, name='polygon_delete'),
    # Batch actions
    path('batch-tag/',                    views.batch_tag,              name='batch_tag'),
    path('batch-delete/',                 views.batch_delete,           name='batch_delete'),

    # Export
    path('project/<int:project_id>/export/yolo/', views.export_yolo, name='export_yolo'),
]
