from django.db import models

from core.models import SluggedModel, TimeStampedModel


class Country(TimeStampedModel, SluggedModel):
    name = models.CharField(max_length=120, unique=True, verbose_name="nome")
    code = models.CharField(max_length=3, unique=True, verbose_name="código")
    alternative_names = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="nomes alternativos",
        help_text="Separe nomes alternativos por vírgula.",
    )
    is_active = models.BooleanField(default=True, verbose_name="ativo")

    class Meta:
        verbose_name = "país"
        verbose_name_plural = "países"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Division(TimeStampedModel, SluggedModel):
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="divisions",
        verbose_name="país",
    )
    name = models.CharField(max_length=120, verbose_name="nome")
    short_name = models.CharField(max_length=30, blank=True, verbose_name="nome curto")
    level = models.PositiveSmallIntegerField(verbose_name="nível")
    alternative_names = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="nomes alternativos",
        help_text="Separe nomes alternativos por vírgula.",
    )
    is_active = models.BooleanField(default=True, verbose_name="ativa")

    class Meta:
        verbose_name = "divisão"
        verbose_name_plural = "divisões"
        ordering = ["country__name", "level", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["country", "name"],
                name="unique_division_name_per_country",
            ),
            models.UniqueConstraint(
                fields=["country", "level"],
                name="unique_division_level_per_country",
            ),
        ]

    def __str__(self):
        if self.short_name:
            return f"{self.country.code} - {self.short_name}"
        return f"{self.country.code} - {self.name}"
