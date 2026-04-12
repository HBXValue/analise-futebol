from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import Country
from clubs.models import Club
from core.models import SluggedModel, TimeStampedModel


class Athlete(TimeStampedModel, SluggedModel):
    class Foot(models.TextChoices):
        RIGHT = "right", "Direita"
        LEFT = "left", "Esquerda"
        BOTH = "both", "Ambas"

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        INACTIVE = "inactive", "Inativo"
        RETIRED = "retired", "Aposentado"

    full_name = models.CharField(max_length=180, verbose_name="nome completo")
    sport_name = models.CharField(max_length=120, blank=True, verbose_name="nome esportivo")
    birth_date = models.DateField(blank=True, null=True, verbose_name="data de nascimento")
    nationality = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="athletes",
        verbose_name="nacionalidade",
    )
    primary_position = models.CharField(max_length=80, verbose_name="posição principal")
    secondary_positions = models.CharField(
        max_length=180,
        blank=True,
        verbose_name="posições secundárias",
        help_text="Separe por vírgula.",
    )
    dominant_foot = models.CharField(
        max_length=10,
        choices=Foot.choices,
        blank=True,
        verbose_name="perna dominante",
    )
    height_cm = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="altura (cm)")
    weight_kg = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="peso (kg)")
    current_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        related_name="current_athletes",
        blank=True,
        null=True,
        verbose_name="clube atual",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="status",
    )
    notes = models.TextField(blank=True, verbose_name="observações")

    class Meta:
        verbose_name = "atleta"
        verbose_name_plural = "atletas"
        ordering = ["sport_name", "full_name"]

    def __str__(self):
        return self.sport_name or self.full_name


class AthleteClubHistory(TimeStampedModel):
    athlete = models.ForeignKey(
        Athlete,
        on_delete=models.CASCADE,
        related_name="club_history",
        verbose_name="atleta",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="athlete_history",
        verbose_name="clube",
    )
    start_date = models.DateField(verbose_name="início")
    end_date = models.DateField(blank=True, null=True, verbose_name="fim")
    shirt_number = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="camisa")
    is_current = models.BooleanField(default=False, verbose_name="vínculo atual")
    notes = models.TextField(blank=True, verbose_name="observações")

    class Meta:
        verbose_name = "histórico do atleta"
        verbose_name_plural = "históricos dos atletas"
        ordering = ["-is_current", "-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["athlete", "club", "start_date"],
                name="unique_athlete_club_period",
            ),
        ]

    def __str__(self):
        return f"{self.athlete} - {self.club}"

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "A data final não pode ser anterior à data inicial."})

        if self.is_current and self.end_date:
            raise ValidationError({"end_date": "Um vínculo atual não pode ter data final."})
