from django.urls import path
from . import views
from . import api_views

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
    path('<int:pk>/annotate/seg/save/',   views.segmentation_save,      name='segmentation_save'),
    path('<int:pk>/annotate/box/<int:box_pk>/delete/', views.annotation_delete_box, name='annotation_delete_box'),
    path('<int:pk>/annotate/polygon/<int:poly_pk>/delete/', views.polygon_delete, name='polygon_delete'),
    # Batch actions
    path('batch-tag/',                    views.batch_tag,              name='batch_tag'),
    path('batch-delete/',                 views.batch_delete,           name='batch_delete'),

    # Export
    path('project/<int:project_id>/export/yolo/', views.export_yolo, name='export_yolo'),
    path('project/<int:project_id>/export/csv/',  views.export_csv,  name='export_csv'),
    path('project/<int:project_id>/export/coco/', views.export_coco, name='export_coco'),
    path('project/<int:project_id>/export/json/', views.export_json, name='export_json'),

    path('<int:image_id>/comments/', views.image_comment, name='image_comment'),

    path('api/upload/', api_views.api_image_upload,                     name='api_image_upload'),
    path('api/token/', api_views.api_token_create,                      name='api_token_create'),
    path('api/token/revoke/', api_views.api_token_revoke,               name='api_token_revoke'),

    # GET  /app/images/api/images/<id>/annotations/  → list all annotations
    # POST /app/images/api/images/<id>/annotations/  → create annotation
    path('api/images/<int:image_id>/annotations/', api_views.api_annotations, name='api_annotations'),

    # DELETE /app/images/api/annotations/bbox/3/
    path('api/annotations/<str:annotation_type>/<int:annotation_id>/', api_views.api_annotation_delete, name='api_annotation_delete'),

]
