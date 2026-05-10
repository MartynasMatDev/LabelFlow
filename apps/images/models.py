import os
import json
from django.db import models
from django.contrib.auth.models import User
from apps.projects.models import Project

import hashlib
import secrets


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=7, default='#6366f1')  # hex colour
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name


class Image(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending annotation'),
        ('partial',  'Partially annotated'),
        ('done',     'Annotated'),
    ]

    project     = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_images')
    image_file  = models.ImageField(upload_to='images/%Y/%m/')
    name        = models.CharField(max_length=255, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    width       = models.PositiveIntegerField(null=True, blank=True)
    height      = models.PositiveIntegerField(null=True, blank=True)
    file_size   = models.PositiveIntegerField(null=True, blank=True, help_text='Bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    tags        = models.ManyToManyField(Tag, blank=True, related_name='images')

    class Meta:
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.name and self.image_file:
            self.name = os.path.basename(self.image_file.name)
        super().save(*args, **kwargs)
        if self.image_file and (not self.width or not self.height):
            try:
                from PIL import Image as PILImage
                with PILImage.open(self.image_file.path) as img:
                    self.width, self.height = img.size
                    Image.objects.filter(pk=self.pk).update(width=self.width, height=self.height)
            except Exception:
                print(Exception)

    def __str__(self):
        return self.name or str(self.pk)

    @property
    def file_size_kb(self):
        if self.file_size:
            return round(self.file_size / 1024, 1)
        return None

    @property
    def resolution(self):
        if self.width and self.height:
            return f"{self.width}\u00d7{self.height}"
        return '\u2014'

    @property
    def preview_boxes_json(self):
        """
        Returns a JSON string of all bounding boxes for this image,
        in the same format used by image_detail.html / image_annotate.html.
        Used by the image list lightbox preview.
        """
        boxes = [b.to_dict() for b in self.bounding_boxes.select_related('label').all()]
        return json.dumps(boxes)


class BoundingBox(models.Model):
    """A single bounding box annotation on an image."""
    image = models.ForeignKey(
        Image,
        on_delete=models.CASCADE,
        related_name='bounding_boxes'
    )
    label = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bounding_boxes',
        help_text='Tag/label for this annotation'
    )
    # Stored as percentages (0-100) - resolution-independent
    x      = models.FloatField(help_text='Left edge as % of image width')
    y      = models.FloatField(help_text='Top edge as % of image height')
    width  = models.FloatField(help_text='Width as % of image width')
    height = models.FloatField(help_text='Height as % of image height')

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_boxes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        label_name = self.label.name if self.label else 'unlabelled'
        return f'{label_name} on {self.image.name} ({self.x:.1f},{self.y:.1f})'

    def to_dict(self):
        return {
            'id':     self.pk,
            'label':  {
                'id':    self.label.id,
                'name':  self.label.name,
                'color': self.label.color,
            } if self.label else None,
            'x':      self.x,
            'y':      self.y,
            'width':  self.width,
            'height': self.height,
        }

class SegmentationMask(models.Model):
    """Per-label pixel mask stored as a base64-encoded PNG."""
    image = models.ForeignKey(
        Image, on_delete=models.CASCADE, related_name='seg_masks'
    )
    label = models.ForeignKey(
        Tag, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='seg_masks'
    )
    mask_data  = models.TextField(help_text='Base64-encoded PNG mask (data: URI)')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_masks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        label_name = self.label.name if self.label else 'unlabelled'
        return f'{label_name} mask on {self.image.name}'

    def to_dict(self):
        return {
            'id':        self.pk,
            'label':     {
                'id':    self.label.id,
                'name':  self.label.name,
                'color': self.label.color,
            } if self.label else None,
            'mask_data': self.mask_data,
        }

    def to_meta(self):
        return {
            'id':    self.pk,
            'label': {
                'id':    self.label.id,
                'name':  self.label.name,
                'color': self.label.color,
            } if self.label else None,
        }


class Polygon(models.Model):
    """A closed polygon annotation on an image."""
    image = models.ForeignKey(
        Image, on_delete=models.CASCADE, related_name='polygons'
    )
    label = models.ForeignKey(
        Tag, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='polygons', help_text='Tag/label for this annotation'
    )
    # List of {x, y} dicts, each 0-100 (% of image dimensions)
    points = models.JSONField(default=list, help_text='List of {x,y} percentage points')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_polygons'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        label_name = self.label.name if self.label else 'unlabelled'
        return f'{label_name} polygon on {self.image.name}'

    def to_dict(self):
        return {
            'id':     self.pk,
            'label':  {
                'id':    self.label.id,
                'name':  self.label.name,
                'color': self.label.color,
            } if self.label else None,
            'points': self.points,
        }

class ImageComment(models.Model):
    """A threaded comment left on an image."""
    image      = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(User,  on_delete=models.SET_NULL, null=True, related_name='image_comments')
    body       = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author} on {self.image}'

    def get_initials(self):
        if not self.author:
            return '??'
        first = self.author.first_name[:1].upper() if self.author.first_name else ''
        last  = self.author.last_name[:1].upper()  if self.author.last_name  else ''
        return (first + last) or self.author.username[:2].upper()

    def to_dict(self):
        return {
            'id':         self.pk,
            'author':     self.author.get_full_name() or self.author.username if self.author else 'Unknown',
            'initials':   self.get_initials(),
            'body':       self.body,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'can_delete': False,   # filled in by the view per-request-user
        }

class APIToken(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    key = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hex digest of the raw token.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"APIToken for {self.user} (active={self.is_active})"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Return the SHA-256 hex digest of *raw_key*."""
        return hashlib.sha256(raw_key.encode()).hexdigest()