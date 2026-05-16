from django.contrib import admin
from django.utils import timezone
from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'published_at', 'updated_at')
    list_filter = ('status', 'author')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'published_at'
    actions = ['make_published', 'make_draft']

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'status'),
        }),
        ('Content', {
            'fields': ('cover_image', 'excerpt', 'content'),
        }),
        ('Timestamps', {
            'fields': ('published_at', 'created_at', 'updated_at'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Publish selected posts')
    def make_published(self, request, queryset):
        for post in queryset:
            post.status = BlogPost.STATUS_PUBLISHED
            if post.published_at is None:
                post.published_at = timezone.now()
            post.save()

    @admin.action(description='Move selected posts back to draft')
    def make_draft(self, request, queryset):
        queryset.update(status=BlogPost.STATUS_DRAFT)
