from django.db import models


class FuelStation(models.Model):
    """A truck stop with its diesel retail price and an (approximate) location.

    The source CSV has no coordinates, so ``lat``/``lng`` are the centroid of the
    station's city, resolved once by the ``load_fuel_stations`` command.
    """

    truckstop_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    price = models.DecimalField(max_digits=7, decimal_places=4, help_text="USD per gallon")
    lat = models.FloatField()
    lng = models.FloatField()

    class Meta:
        ordering = ["state", "city", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state}) ${self.price}"
