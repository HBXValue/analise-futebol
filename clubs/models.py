from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import Country, Division
from core.models import SluggedModel, TimeStampedModel


class Club(TimeStampedModel, SluggedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        INACTIVE = "inactive", "Inativo"

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="clubs",
        verbose_name="país",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name="clubs",
        verbose_name="divisão",
    )
    official_name = models.CharField(max_length=180, verbose_name="nome oficial")
    short_name = models.CharField(max_length=80, blank=True, verbose_name="nome curto")
    state = models.CharField(max_length=120, blank=True, verbose_name="estado")
    city = models.CharField(max_length=120, blank=True, verbose_name="cidade")
    founded_year = models.PositiveIntegerField(blank=True, null=True, verbose_name="ano de fundação")
    badge_url = models.URLField(blank=True, verbose_name="URL do escudo")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="status",
    )
    notes = models.TextField(blank=True, verbose_name="observações")

    class Meta:
        verbose_name = "clube"
        verbose_name_plural = "clubes"
        ordering = ["country__name", "division__level", "official_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["division", "official_name"],
                name="unique_club_name_per_division",
            ),
        ]

    def __str__(self):
        return self.short_name or self.official_name

    def clean(self):
        super().clean()
        if self.division_id and self.country_id and self.division.country_id != self.country_id:
            raise ValidationError(
                {"division": "A divisão selecionada precisa pertencer ao mesmo país do clube."}
            )
