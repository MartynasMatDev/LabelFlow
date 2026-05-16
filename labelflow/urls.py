from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from apps.images.views import (
    public_export_yolo,
    public_export_csv,
    public_export_coco,
    public_export_json,
)
from apps.projects.views import public_share_landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    path('api-docs/', TemplateView.as_view(template_name='api_docs.html'), name='api_docs'),
    path('accounts/', include('apps.accounts.urls')),
    path('oauth/', include('allauth.urls')),
    path('app/', include('apps.projects.urls')),
    path('app/images/', include('apps.images.urls')),
    path('invite/', include('apps.projects.invitation_urls')),
    path('share/<uuid:share_token>/',         public_share_landing, name='public_share_landing'),
    path('share/<uuid:share_token>/yolo.zip', public_export_yolo, name='public_export_yolo'),
    path('share/<uuid:share_token>/csv.zip',  public_export_csv,  name='public_export_csv'),
    path('share/<uuid:share_token>/coco.zip', public_export_coco, name='public_export_coco'),
    path('share/<uuid:share_token>/json.zip', public_export_json, name='public_export_json'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)