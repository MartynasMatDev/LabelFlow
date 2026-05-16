from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import BlogPost


def _published_qs():
    return BlogPost.objects.filter(status=BlogPost.STATUS_PUBLISHED)


def blog_list(request):
    qs = _published_qs()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(content__icontains=q))
    paginator = Paginator(qs, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'blog/blog_list.html', {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'query': q,
    })


def blog_detail(request, slug):
    post = get_object_or_404(_published_qs(), slug=slug)
    related = _published_qs().exclude(pk=post.pk)[:3]
    return render(request, 'blog/blog_detail.html', {
        'post': post,
        'related': related,
    })
