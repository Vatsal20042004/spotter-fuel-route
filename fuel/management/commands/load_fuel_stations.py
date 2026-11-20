from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from fuel.models import FuelStation
from fuel.services.geodata import Gazetteer, read_price_csv

DATA = Path(settings.BASE_DIR) / "data"


class Command(BaseCommand):
    help = "Load fuel prices from the CSV and place each station using the Census gazetteer."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=DATA / "fuel-prices-for-be-assessment.csv")
        parser.add_argument(
            "--gazetteer",
            nargs="+",
            default=[
                DATA / "us_places_gazetteer_2023.txt",
                DATA / "us_county_subdivisions_gazetteer_2023.txt",
            ],
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        records, stats = read_price_csv(Path(opts["csv"]))
        gaz = Gazetteer.from_files(*map(Path, opts["gazetteer"]))

        stations, unmatched = [], []
        for r in records:
            place = gaz.locate(r.city, r.state)
            if place is None:
                unmatched.append(r)
                continue
            stations.append(
                FuelStation(
                    truckstop_id=r.truckstop_id, name=r.name, address=r.address, city=r.city,
                    state=r.state, price=r.price, lat=place.lat, lng=place.lng,
                )
            )

        FuelStation.objects.all().delete()
        FuelStation.objects.bulk_create(stations, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(stations)} stations"))
        self.stdout.write(
            f"  CSV rows: {stats['rows']} | non-US dropped: {stats['non_us']} | "
            f"duplicate IDs merged: {stats['duplicates']} | bad rows: {stats['bad_rows']}"
        )
        self.stdout.write(f"  Skipped (city not in gazetteer; never mis-located): {len(unmatched)}")
