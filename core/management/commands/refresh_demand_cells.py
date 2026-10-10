import math
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import BusinessLocation, CustomerBusiness, DemandCell


class Command(BaseCommand):
    help = (
        "Refresh approximate public demand cells; only cells with at least three prospects "
        "are stored."
    )

    def handle(self, *args, **options):
        step_m = 500
        lat_step = step_m / 111_320
        counts = Counter()
        locations = (
            BusinessLocation.objects.filter(
                business__status__in=[
                    CustomerBusiness.Status.SUBMITTED,
                    CustomerBusiness.Status.REVIEWED,
                    CustomerBusiness.Status.SCHEDULED,
                ]
            )
            .values_list("latitude", "longitude")
            .iterator()
        )
        for raw_lat, raw_lng in locations:
            lat, lng = float(raw_lat), float(raw_lng)
            lat_index = math.floor(lat / lat_step)
            center_lat = (lat_index + 0.5) * lat_step
            lon_step = min(180, lat_step / max(0.1, math.cos(math.radians(center_lat))))
            lon_index = math.floor(lng / lon_step)
            counts[(lat_index, lon_index)] += 1

        cells = []
        for (lat_index, lon_index), count in counts.items():
            if count < 3:
                continue
            south, north = lat_index * lat_step, (lat_index + 1) * lat_step
            center_lat = (south + north) / 2
            lon_step = min(180, lat_step / max(0.1, math.cos(math.radians(center_lat))))
            west, east = lon_index * lon_step, (lon_index + 1) * lon_step
            cell_id = f"{lat_index}:{lon_index}"
            geojson = {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[west, south], [east, south], [east, north], [west, north], [west, south]]
                    ],
                },
            }
            level = "low" if count < 6 else "med" if count < 15 else "high"
            cells.append(
                DemandCell(cell_id=cell_id, geojson=geojson, request_count=count, level=level)
            )

        with transaction.atomic():
            DemandCell.objects.all().delete()
            DemandCell.objects.bulk_create(cells)
        self.stdout.write(
            f"Refreshed {len(cells)} aggregate cells (raw request counts are not exposed publicly)."
        )
