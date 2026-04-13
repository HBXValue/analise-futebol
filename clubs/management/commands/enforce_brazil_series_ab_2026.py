import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from athletes.models import Athlete, AthleteClubHistory
from catalog.models import Country, Division
from clubs.models import Club
from valuation.models import Player


SERIES = {
    1: [
        "Palmeiras", "Fluminense", "Bahia", "São Paulo", "Atletico Pr", "Flamengo",
        "Coritiba", "Vasco da Gama", "Atletico Mg", "Grêmio", "Bragantino", "Vitória Ba",
        "Santos", "Corinthians", "Botafogo", "Internacional", "Cruzeiro", "Chapecoense",
        "Mirasol", "Remo",
    ],
    2: [
        "Botafogo SP", "Avaí", "Operário", "Goias", "Londrina", "Athletic", "Criciuma",
        "Náutico", "Vila Nova", "Ceará", "Sport Recife", "Cuiabá", "São Bernardo", "CRB",
        "Ponte Preta", "Novo Horizontino", "Juventude", "Fortaleza", "Atlético Go", "América Mg",
    ],
    3: [
        "Inter Limeira", "Confiança", "Amazonas", "Anápolis", "Itabaiana", "Barra",
        "Botafogo- PB", "Brusque", "Ferroviária", "Figueirense", "Floresta", "Guarani",
        "Ituano", "Maranhão", "Maringá", "Paysandu", "Santa Cruz", "Caxias",
        "Volta Redonda", "Ypiranga",
    ],
    4: [
        "Manaura", "Manaus", "Monte Roraima", "Nacional", "Sampaio", "São Raimundo",
        "Araguaiana", "Galvez", "Gazin Porto Velho", "Guaporé", "Humaitá", "Independência",
        "Aparacidense", "Brasiliense", "Gama", "Inhumas EC", "Luverdense", "Primavera Atl. Clube",
        "Capital", "Ceilândia SAF", "Goiatuba", "Mixto", "Operário MT", "União",
        "Aguia de Marabá", "Imperatriz", "Oratório", "Tocantinópolis", "Trem", "Tunaluso",
        "Iape", "Iguatu", "Maracanã", "Moto Clube", "Parnahyba", "Sampaio Corrêa",
        "Altos", "FC Atletico Cearense", "Ferroviário", "Fluminense", "Piauí", "Tirol",
        "ABC", "América FC SAF", "Central de Caruarú", "Laguna", "Maguary", "Sousa",
        "Decisão", "Lagarto", "Retrô", "Sergipe", "Serra Branca EC", "Treze",
        "Asa", "Atlético Alagoinhas", "CSA", "CSE", "Jacuipense", "Juazeirense",
        "Abecat", "Betim", "Crac", "Ivinhema", "Operário MS", "Uberlandia",
        "FC Democrata", "Porto SC", "Real Noroeste Capixaba", "Rio Branco Ac", "Tombense", "Vitória FC",
        "Agua Santa", "América", "Madureira", "Portuguesa", "Portuguesa SAF", "Pouso Alegre SAF",
        "Marica", "Noroeste", "Nova Iguaçu SAF", "Sampaio Correa", "Velo Clube", "XV de Piracicaba",
        "Cascavel", "Guarany FC", "Joinville", "Leão do vale- Cianorte", "Santa Catarina Clube", "São Luiz",
        "Azuriz", "Blumenau", "Brasil de Pelotas", "Marcilio dias", "São José", "Sãojoseense",
    ],
}


ALIASES = {
    "atletico pr": {"athletico paranaense", "athletico-pr"},
    "atletico mg": {"clube atletico mineiro", "atletico-mg"},
    "vasco da gama": {"club de regatas vasco da gama", "vasco"},
    "vitoria ba": {"esporte clube vitoria", "vitoria"},
    "mirasol": {"mirassol futebol clube", "mirassol"},
    "botafogo sp": {"botafogo futebol clube", "botafogo-sp"},
    "avai": {"avai futebol clube"},
    "operario": {"operario ferroviario esporte clube"},
    "nautico": {"clube nautico capibaribe", "nautico"},
    "ceara": {"ceara sporting club"},
    "sport recife": {"sport club do recife", "sport"},
    "atletico go": {"atletico clube goianiense", "atletico-go"},
    "america mg": {"america futebol clube", "america-mg"},
    "confianca": {"confianca"},
    "anapolis": {"anapolis"},
    "ferroviaria": {"ferroviaria"},
    "maranhao": {"maranhao"},
    "maringa": {"maringa"},
}


def normalize(value):
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").split())


def move_references(source, target):
    Athlete.objects.filter(current_club=source).update(current_club=target)
    AthleteClubHistory.objects.filter(club=source).update(club=target)
    Player.objects.filter(club_reference=source).update(
        club_reference=target,
        club_origin=target.short_name or target.official_name,
        league_level=target.division.short_name or target.division.name,
        division_reference=target.division,
    )


class Command(BaseCommand):
    help = "Alinha Séries A, B, C e D do Brasil exatamente com as listas oficiais definidas para 2026."

    @transaction.atomic
    def handle(self, *args, **options):
        brazil = Country.objects.filter(code="BRA").first()
        if brazil is None:
            raise CommandError("País BRA não encontrado.")

        kept_total = 0
        removed_total = 0

        for level, desired_names in SERIES.items():
            division = Division.objects.filter(country=brazil, level=level).first()
            if division is None:
                raise CommandError(f"Divisão brasileira de nível {level} não encontrada.")

            clubs = list(Club.objects.filter(country=brazil, division=division).order_by("id"))
            chosen_ids = set()

            for desired_name in desired_names:
                desired_key = normalize(desired_name)
                candidate_keys = {desired_key} | ALIASES.get(desired_key, set())
                exact_official = None
                exact_short = None
                alias_match = None

                for club in clubs:
                    if club.id in chosen_ids:
                        continue
                    official_key = normalize(club.official_name)
                    short_key = normalize(club.short_name)
                    if official_key == desired_key:
                        exact_official = club
                        break
                    if short_key == desired_key and exact_short is None:
                        exact_short = club
                    if ({official_key, short_key} & candidate_keys) and alias_match is None:
                        alias_match = club

                matched = exact_official or exact_short or alias_match

                if matched is None:
                    matched = Club.objects.create(
                        country=brazil,
                        division=division,
                        official_name=desired_name,
                        short_name=desired_name,
                        status=Club.Status.ACTIVE,
                    )
                    clubs.append(matched)

                existing_exact = next(
                    (
                        club for club in clubs
                        if club.id != matched.id
                        and club.id not in chosen_ids
                        and normalize(club.official_name) == desired_key
                    ),
                    None,
                )
                if existing_exact is None:
                    matched.official_name = desired_name
                matched.short_name = desired_name
                matched.status = Club.Status.ACTIVE
                matched.save()
                chosen_ids.add(matched.id)
                kept_total += 1

            canonical_by_key = {}
            for club in Club.objects.filter(country=brazil, division=division, id__in=chosen_ids):
                canonical_by_key[normalize(club.short_name or club.official_name)] = club

            for club in Club.objects.filter(country=brazil, division=division).exclude(id__in=chosen_ids):
                club_key = normalize(club.short_name or club.official_name)
                target = None
                for desired_key, canonical in canonical_by_key.items():
                    if club_key == desired_key or club_key in ALIASES.get(desired_key, set()):
                        target = canonical
                        break
                if target is not None:
                    move_references(club, target)
                club.delete()
                removed_total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Alinhamento concluído: {kept_total} clubes mantidos/criados nas Séries A, B, C e D, {removed_total} excedentes removidos."
            )
        )
