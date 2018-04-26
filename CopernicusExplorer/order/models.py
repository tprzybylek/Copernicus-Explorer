from django.contrib.gis.db.models import PolygonField
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

    def __str__(self):
        return self.pk


class ProductOrder(models.Model):
    product_id = models.ForeignKey(Product, on_delete='CASCADE')
    order_id = models.ForeignKey(Order, on_delete='CASCADE')

    def __str__(self):
        return self.product_id
