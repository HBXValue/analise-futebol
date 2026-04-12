from django.contrib import admin

from catalog.models import Country, Division


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "alternative_names", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "country", "level", "is_active")
    list_filter = ("country", "level", "is_active")
    search_fields = ("name", "short_name", "alternative_names", "country__name", "slug")
    autocomplete_fields = ("country",)
    prepopulated_fields = {"slug": ("name",)}
