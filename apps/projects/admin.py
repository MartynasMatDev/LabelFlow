from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('name', 'created_by', 'annotation_type', 'member_count', 'image_count', 'created_at')
    list_filter   = ('annotation_type',)
    search_fields = ('name', 'created_by__username')
    #inlines       = [ProjectMemberInline]


