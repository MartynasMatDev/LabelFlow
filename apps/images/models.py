import os
import json
from django.db import models
from django.contrib.auth.models import User
from apps.projects.models import Project


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