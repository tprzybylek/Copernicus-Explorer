from django.contrib.gis.db import models

# Create your models here.


class Product(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    title = models.CharField(max_length=67)
    ingestion_date = models.DateTimeField()
    satellite = models.CharField(max_length=3)
    mode = models.CharField(max_length=8)
    orbit_direction = models.CharField(max_length=10)
    cloud_cover = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    polarisation_mode = models.CharField(max_length=5, blank=True, null=True)
    product_type = models.CharField(max_length=7)
    relative_orbit_number = models.IntegerField()
    size = models.BigIntegerField()
    coordinates = models.PolygonField()

    def __str__(self):
        return self.id
