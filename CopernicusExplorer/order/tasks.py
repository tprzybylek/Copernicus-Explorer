from __future__ import absolute_import, unicode_literals
from celery import shared_task

import sys
import os

sys.path.append('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/modules')
import imageryutil

from .models import Order, ProductOrder, Product


@shared_task
def perform_order(order_id):
    # get order by id
    order = Order.objects.filter(pk=order_id)[0]

    # set order status to PENDING
    order.status = 1
    order.save()

    # get ids of ordered products

    #productorder = ProductOrder.objects.filter(order_id=order_id)

    products = order.products.all()

    print(products)

    # for each product in ordered products

    #products = []
    #for product in productorder:
        #products.append(product.product_id)

    #product = Product.objects.filter(id__in=products)

    for p in products:
        #   download product (if not already downloaded)

        if not os.path.isfile(os.path.join(imageryutil.DOWNLOAD_DIR, p.id + '.zip')):
            print('Product is being downloaded')
            imageryutil.download_product(p.id)

        if not os.path.exists(os.path.join(imageryutil.DOWNLOAD_DIR, p. id, p.title + '.SAFE')):
            print('Product is being extracted')
            imageryutil.unzip_product(p.id)

        #   clip product
        imageryutil.iterate_product(p, order)

    # zip order
    imageryutil.zip_order(order_id)

    # delete order directory

    # set order status to COMPLETE
    order.status = 2
    order.save()
