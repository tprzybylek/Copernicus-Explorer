#from django.db import models
from django.contrib.gis.db import models

# Create your models here.

class ImageS1(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    title = models.CharField(max_length=67)
    ingestiondate = models.DateTimeField()
    satellite = models.CharField(max_length=3)
    mode = models.CharField(max_length=2)
    orbitdirection = models.CharField(max_length=10)
    polarisationmode = models.CharField(max_length=5)
    producttype = models.CharField(max_length=3)
    relativeorbitnumber = models.IntegerField()
    size =  models.BigIntegerField()
    coordinates =  models.PolygonField()
    def __str__(self):
        return self.id

class ImageS2(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    title = models.CharField(max_length=60)
    ingestiondate = models.DateTimeField()
    satellite = models.CharField(max_length=3)
    mode = models.CharField(max_length=8)
    orbitdirection = models.CharField(max_length=10)
    cloudcover = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    producttype = models.CharField(max_length=7)
    relativeorbitnumber = models.IntegerField()
    size =  models.BigIntegerField()
    coordinates =  models.PolygonField()
    def __str__(self):
        return self.id