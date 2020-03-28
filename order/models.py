from django.contrib.gis.db.models import PolygonField
from django.contrib.postgres.fields import ArrayField
from django.db import models
from search.models import Product


class Order(models.Model):
    e_mail = models.EmailField()
    ordered_date_time = models.DateTimeField()
    completed_date_time = models.DateTimeField(null=True, blank=True)

    STATUS_WAITING = 0
    STATUS_PENDING = 1
    STATUS_COMPLETE = 2
    STATUS_ERR = 3

    STATUS_CHOICES = (
        (STATUS_WAITING, 'Waiting'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_ERR, 'Err')
    )

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES)
    clip_extent = PolygonField()
    layers = ArrayField(models.CharField(max_length=8), null=True, blank=True)
    products = models.ManyToManyField(Product)

    def __str__(self):
        return str(self.pk)

    def extent(self):
        extent = self.clip_extent.extent
        return {
            'min_x': extent[0],
            'min_y': extent[1],
            'max_x': extent[2],
            'max_y': extent[3]
        }


class ProductOrder(models.Model):
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE)
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE)

    def __str__(self):
        return self.product_id
