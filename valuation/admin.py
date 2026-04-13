from django.contrib import admin

from valuation.models import (
    BehaviorMetrics,
    CareerIntelligenceCase,
    CareerPrognosis,
    ClubCompetitiveContext,
    CoachProfile,
    CompetitiveDiagnosis,
    IndividualDevelopmentPlan,
    MarketMetrics,
    MarketingMetrics,
    PerformanceMetrics,
    Player,
    PositionCompetitor,
    TacticalGameModel,
    User,
)


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
    list_display = ("name", "user", "position", "current_value", "league_level", "club_origin", "division_reference", "club_reference")
    list_filter = ("position", "league_level", "division_reference")
    search_fields = ("name", "club_origin", "user__email")
    inlines = [PerformanceMetricsInline, MarketMetricsInline, MarketingMetricsInline, BehaviorMetricsInline]


@admin.register(CareerIntelligenceCase)
class CareerIntelligenceCaseAdmin(admin.ModelAdmin):
    list_display = ("athlete_name", "user", "current_club", "current_step", "updated_at")
    list_filter = ("current_step", "category", "squad_status")
    search_fields = ("athlete_name", "current_club", "user__email")


admin.site.register(ClubCompetitiveContext)
admin.site.register(CoachProfile)
admin.site.register(TacticalGameModel)
admin.site.register(PositionCompetitor)
admin.site.register(CompetitiveDiagnosis)
admin.site.register(CareerPrognosis)
admin.site.register(IndividualDevelopmentPlan)
