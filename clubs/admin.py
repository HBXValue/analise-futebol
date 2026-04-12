from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from athletes.models import Athlete, AthleteClubHistory
from clubs.models import Club


class CurrentAthleteInline(admin.TabularInline):
    model = Athlete
    fk_name = "current_club"
    extra = 0
    fields = ("athlete_link", "primary_position", "status", "birth_date")
    readonly_fields = ("athlete_link",)
    show_change_link = True

    def athlete_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:athletes_athlete_change", args=[obj.pk])
        label = obj.sport_name or obj.full_name
        return format_html('<a href="{}">{}</a>', url, label)

    athlete_link.short_description = "atleta"


class AthleteHistoryInline(admin.TabularInline):
    model = AthleteClubHistory
    extra = 0
    fields = ("athlete_link", "start_date", "end_date", "shirt_number", "is_current")
    readonly_fields = ("athlete_link",)
    autocomplete_fields = ("athlete",)
    show_change_link = True

    def athlete_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:athletes_athlete_change", args=[obj.athlete_id])
        return format_html('<a href="{}">{}</a>', url, obj.athlete)

    athlete_link.short_description = "atleta"


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = (
        "official_name",
        "short_name",
        "country",
        "division",
        "current_athletes_count",
        "state",
        "city",
        "status",
    )
    list_filter = ("country", "division", "status", "state")
    search_fields = (
        "official_name",
        "short_name",
        "city",
        "state",
        "division__name",
        "division__short_name",
        "slug",
    )
    autocomplete_fields = ("country", "division")
    prepopulated_fields = {"slug": ("official_name",)}
    inlines = [CurrentAthleteInline, AthleteHistoryInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("current_athletes")

    def current_athletes_count(self, obj):
        return obj.current_athletes.count()

    current_athletes_count.short_description = "atletas atuais"
