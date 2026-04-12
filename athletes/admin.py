from django.contrib import admin

from athletes.models import Athlete, AthleteClubHistory


class AthleteClubHistoryInline(admin.TabularInline):
    model = AthleteClubHistory
    extra = 0
    autocomplete_fields = ("club",)


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ("full_name", "sport_name", "nationality", "primary_position", "current_club", "status")
    list_filter = ("nationality", "primary_position", "status", "dominant_foot")
    search_fields = ("full_name", "sport_name", "primary_position", "secondary_positions", "slug")
    autocomplete_fields = ("nationality", "current_club")
    prepopulated_fields = {"slug": ("full_name",)}
    inlines = [AthleteClubHistoryInline]


@admin.register(AthleteClubHistory)
class AthleteClubHistoryAdmin(admin.ModelAdmin):
    list_display = ("athlete", "club", "start_date", "end_date", "is_current")
    list_filter = ("is_current", "club")
    search_fields = ("athlete__full_name", "athlete__sport_name", "club__official_name")
    autocomplete_fields = ("athlete", "club")
