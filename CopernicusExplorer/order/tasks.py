from __future__ import absolute_import, unicode_literals
from celery import shared_task

import sys
import os
from django.utils import timezone

sys.path.append('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/modules')
import imageryutil

from .models import Order, ProductOrder, Product


@shared_task
def perform_order(order_id):
    # get order by its ID
    order = Order.objects.filter(pk=order_id)[0]

    # set order status to PENDING
    order.status = 1
    order.save()

    # get IDs of ordered products

    products = order.products.all()

    for p in products:
        #   download product (if not already downloaded)

        if not os.path.isfile(os.path.join(imageryutil.TEMP_DIR, p.id + '.zip')):
            print('Product is being downloaded')
            imageryutil.download_product(p.id)

        if not os.path.exists(os.path.join(imageryutil.TEMP_DIR, p. id, p.title + '.SAFE')):
            print('Product is being extracted')
            imageryutil.unzip_product(p.id)

        #   clip product
        imageryutil.iterate_product(p, order)

    # zip order
    imageryutil.zip_order(order_id)

    # delete order directory


    # set order status to COMPLETE
    order.completed_date_time = timezone.now()
    order.status = 2
    order.save()
