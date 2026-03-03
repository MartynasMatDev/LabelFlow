from django.contrib import admin
from .models import Image


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display  = ('name', 'project', 'uploaded_by', 'status', 'resolution', 'file_size_kb', 'uploaded_at')
    list_filter   = ('status', 'project')
    search_fields = ('name', 'project__name')
    readonly_fields = ('uploaded_at', 'width', 'height', 'file_size')
