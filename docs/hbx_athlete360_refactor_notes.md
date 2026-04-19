# HBX Athlete 360 Refactor Notes

## Why This Refactor Exists

HBX evolved with strong modules, but they accumulated repeated athlete context, duplicated inputs, weak cross-module synchronization, and scattered source-of-truth logic.  
This refactor introduces a domain-centered architecture underneath the current platform without breaking current usage.

## New Core Architecture

- `Athlete360Core`
- `Athlete360Orchestrator`
- `AthleteSnapshot` as consolidated historical state
- `TeamContextSnapshot`
- `PerformanceAggregate`
- `BehavioralAggregate`
- `MarketAggregate`
- `MarketingAggregate`
- `ProjectionAggregate`
- `OpportunityAggregate`

## Migration Plan

### Phase 1
- Create new core and aggregate models.
- Expand `AthleteSnapshot` to store consolidated summaries.
- Add source-category normalization.
- Keep legacy modules writing as before.
- Run orchestrator automatically from existing save flows.

### Phase 2
- Make `Athletes` consume `Athlete360Core` and `TeamContextSnapshot` as read-first tabs.
- Introduce `Overview` and `Team Context` as official consolidated tabs.
- Keep legacy edit fields while consolidation runs underneath.

### Phase 3
- Move Dashboard to pure executive read mode.
- Redirect operational writes to dedicated modules:
  - `DevelopmentPlan`
  - `ProgressTracking`
  - `ScenarioLab`

### Phase 4
- Migrate `Match Analysis`, `Performance Intelligence`, `Market Intelligence`, `Reports` and future Base44 / Go Carriera ingestions to read from aggregates and snapshots first.

## Fields Becoming Redundant Over Time

These are not removed yet, but should progressively stop being treated as independent module context:

- repeated club / league / category / squad status inputs outside `Athlete360Core`
- scattered tactical context in:
  - athlete profile
  - match analysis
  - performance intelligence
- repeated contract timing logic across:
  - player profile
  - market logic
  - opportunity logic
- repeated comparison windows assembled independently in Dashboard / Reports

## Suggested Cleanup List

1. Stop using module-local club/league/status context as source-of-truth.
2. Replace ad hoc team-context reads with `TeamContextSnapshot`.
3. Make Dashboard read-only for executive use.
4. Replace scattered summary assembly with `AthleteSnapshot`.
5. Centralize source tracing using:
   - `internal_manual`
   - `base44_registry`
   - `go_carriera`
   - `imported_csv`
   - `generated_by_hbx`
   - `ai_interpretation`

## Future Integration Targets

### Base44
- registry identity
- club and league registry
- tactical environment
- team context

### Go Carriera
- readiness
- habits
- emotional stability
- injury behavior
- adherence
- consistency

Both integrations should write into the new orchestration layer instead of updating module-specific state directly.
