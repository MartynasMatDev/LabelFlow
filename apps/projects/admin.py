from django.contrib import admin
from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('name', 'created_by', 'annotation_type', 'member_count', 'image_count', 'created_at')
    list_filter   = ('annotation_type',)
    search_fields = ('name', 'created_by__username')
    inlines       = [ProjectMemberInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'project', 'role', 'joined_at')
    list_filter   = ('role',)
    search_fields = ('user__username', 'project__name')
