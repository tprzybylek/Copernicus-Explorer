import random
from django.contrib.gis.db import models
from django.db import IntegrityError
from datetime import datetime


class ProductOrder(models.Model):
    ImageID = models.CharField(max_length=36)
    OrderID = models.IntegerField()
    def __str__(self):
        return '%s %s' % (self.imageID, self.orderID)

class Order(models.Model):
    OrderID = models.AutoField(primary_key=True)
    Email = models.CharField(max_length=50)
    OrderedDateTime = datetime.now()
    CompletedDateTime = models.DateTimeField()
    ClipExtent = models.PolygonField()
