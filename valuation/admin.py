from django.contrib import admin

from valuation.models import BehaviorMetrics, MarketMetrics, MarketingMetrics, PerformanceMetrics, Player, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email",)
    search_fields = ("email",)


class PerformanceMetricsInline(admin.StackedInline):
    model = PerformanceMetrics
    extra = 0


class MarketMetricsInline(admin.StackedInline):
    model = MarketMetrics
    extra = 0


class MarketingMetricsInline(admin.StackedInline):
    model = MarketingMetrics
    extra = 0


class BehaviorMetricsInline(admin.StackedInline):
    model = BehaviorMetrics
    extra = 0


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "position", "current_value", "league_level")
    list_filter = ("position", "league_level")
    search_fields = ("name", "club_origin", "user__email")
    inlines = [PerformanceMetricsInline, MarketMetricsInline, MarketingMetricsInline, BehaviorMetricsInline]
