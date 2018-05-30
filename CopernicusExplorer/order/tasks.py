from __future__ import absolute_import, unicode_literals
from celery import shared_task

import sys
sys.path.append('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/modules')
import imageryutil


from datetime import datetime
from datetime import timedelta
import psycopg2
import time

from .models import Order, ProductOrder, Product


@shared_task
def perform_order(order_id):
    # get order by id
    order = Order.objects.filter(pk=order_id)[0]
    print(order.pk)
    print(order.ordered_date_time)
    print(order.e_mail)

    # set order status to PENDING
    order.status = 1
    order.save()

    # get ids of ordered products

    productorder = ProductOrder.objects.filter(order_id=order_id)

    # for each product in ordered products

    products = []
    for product in productorder:
        products.append(product.product_id)

    product = Product.objects.filter(id__in=products)

    for p in product:
        #   download product (if not already downloaded)

        if imageryutil.is_downloaded(p.id):
            pass
        else:
            imageryutil.download_product(p.id)

        #   clip product
        if p.satellite[:2] == 'S1':
            # imageryutil.clipImageTiff()
            pass
        elif p.satellite[:2] == 'S2':
            # imageryutil.clipImageJP2()
            pass
        else:
            order.status = 3
            order.save()

    # zip order
    # imageryutil.zip_order(order_id)

    # set order status to COMPLETE

    order.status = 2
    order.save()
