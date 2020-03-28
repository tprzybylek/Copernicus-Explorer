from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField

# Create your models here.


class Product(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    title = models.CharField(max_length=100)
    ingestion_date = models.DateTimeField(blank=True, null=True)
    satellite = models.CharField(max_length=3)
    mode = models.CharField(max_length=8)
    orbit_direction = models.CharField(max_length=10)
    cloud_cover = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    # polarisation_mode = models.CharField(max_length=5, blank=True, null=True)
    polarisation_mode = ArrayField(models.CharField(max_length=2, blank=True, null=True), blank=True, null=True)
    product_type = models.CharField(max_length=8)
    relative_orbit_number = models.IntegerField()
    size = models.BigIntegerField()
    coordinates = models.PolygonField()
    sensing_date = models.DateTimeField(blank=True, null=True)
    is_downloaded = models.BooleanField(default=False)

    def __str__(self):
        return self.id


class AdministrativeUnit(models.Model):
    gml_id = models.CharField(max_length=64, primary_key=True)
    unit_type = models.CharField(max_length=64)
    unit_code = models.IntegerField()
    unit_name = models.CharField(max_length=64)

    poly = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.unit_name

class UpdateLog(models.Model):
    log_date = models.DateTimeField()
    status = models.SmallIntegerField()
