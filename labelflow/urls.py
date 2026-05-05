from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from apps.images.views import public_export_yolo

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    path('accounts/', include('apps.accounts.urls')),
    path('oauth/', include('allauth.urls')),
    path('app/', include('apps.projects.urls')),
    path('app/images/', include('apps.images.urls')),
    path('invite/', include('apps.projects.invitation_urls')),
    path('share/<uuid:share_token>/yolo.zip', public_export_yolo, name='public_export_yolo'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)