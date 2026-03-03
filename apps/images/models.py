# information about image itself
import os
from django.db import models
from django.contrib.auth.models import User
from apps.projects.models import Project


class Image(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Laukia anotavimo'),
        ('partial',  'Dalinai anotavota'),
        ('done',     'Anotavota'),
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

    class Meta:
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.name and self.image_file:
            self.name = os.path.basename(self.image_file.name)
        super().save(*args, **kwargs)
        # Try to read image dimensions after save
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
            return f"{self.width}×{self.height}"
        return '—'
