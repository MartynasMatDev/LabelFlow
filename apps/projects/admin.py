from django.contrib import admin
from .models import Project, ProjectMember, Workspace, WorkspaceMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('name', 'workspace', 'created_by', 'annotation_type', 'member_count', 'image_count', 'created_at')
    list_filter   = ('annotation_type', 'workspace')
    search_fields = ('name', 'created_by__username', 'workspace__name')
    inlines       = [ProjectMemberInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'project', 'role', 'joined_at')
    list_filter   = ('role',)
    search_fields = ('user__username', 'project__name')


class WorkspaceMemberInline(admin.TabularInline):
    model = WorkspaceMember
    extra = 1


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display  = ('name', 'kind', 'owner', 'project_count', 'member_count', 'created_at')
    list_filter   = ('kind',)
    search_fields = ('name', 'owner__username')
    inlines       = [WorkspaceMemberInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'workspace', 'role', 'joined_at')
    list_filter   = ('role',)
    search_fields = ('user__username', 'workspace__name')
