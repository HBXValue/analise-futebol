from django.db import models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="atualizado em")

    class Meta:
        abstract = True


class SluggedModel(models.Model):
    slug = models.SlugField(max_length=180, unique=True, blank=True, verbose_name="slug")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.build_unique_slug()
        super().save(*args, **kwargs)

    def build_unique_slug(self):
        base_slug = slugify(str(self))
        if not base_slug:
            base_slug = self.__class__.__name__.lower()
        slug = base_slug
        counter = 2
        while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug
