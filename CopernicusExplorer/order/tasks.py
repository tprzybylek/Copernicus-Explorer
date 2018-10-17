from __future__ import absolute_import, unicode_literals
from celery import shared_task

import os
import sys
import shutil
import zipfile
import requests
import json
import numpy
from osgeo import ogr, osr, gdal

from django.utils import timezone
from django.conf import settings
from .models import Order, ProductOrder, Product

# os.path.join(BASE_DIR, ...)

BASE_DIR = settings.BASE_DIR
TEMP_DIR = os.path.join(BASE_DIR, 'data/temp')
ORDERS_DIR = os.path.join(BASE_DIR, 'data/orders')
IMAGERY_DIR = os.path.join(BASE_DIR, 'data/imagery')


def download_product(product_id):
    """
    Downloads a Sentinel product from ESA archive and writes it to the hard drive
    :param str product_id: Product ID
    """

    url = "https://scihub.copernicus.eu/dhus/odata/v1/Products('" + product_id + "')/$value"

    passwords = json.load(open(os.path.join(BASE_DIR, 'passwords.json')))

    username = passwords['scihub']['user']
    password = passwords['scihub']['password']

    r = requests.get(url, auth=(username, password), stream=True)
    if r.status_code == 200:
        if os.path.exists(TEMP_DIR) == False:
            os.makedirs(TEMP_DIR)

        with open(os.path.join(TEMP_DIR, product_id + '.zip'), 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

    sys.stdout.flush()


def unzip_product(product_id):
    """
    Unzips the product to /TEMP_DIR/product_id/
    :param str product_id: Product ID
    """

    if os.path.exists(TEMP_DIR) == False:
        os.makedirs(TEMP_DIR)

    zip_ref = zipfile.ZipFile(os.path.join(TEMP_DIR, product_id + '.zip'), 'r')
    zip_ref.extractall(os.path.join(TEMP_DIR, product_id))
    zip_ref.close()


def zip_order(order_id):
    """
    Zips a requested order to the /ORDERS_PATH/order_id.zip file
    :param str order_id: Order ID
    """

    folder_path = os.path.join(ORDERS_DIR, str(order_id))
    output_path = os.path.join(ORDERS_DIR, str(order_id) + '.zip')

    parent_folder = os.path.dirname(folder_path)

    contents = os.walk(folder_path)

    try:
        zip_file = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)
        for root, folders, files in contents:
            for folder_name in folders:
                absolute_path = os.path.join(root, folder_name)
                relative_path = absolute_path.replace(parent_folder + '/', '')
                zip_file.write(absolute_path, relative_path)

            for file_name in files:
                absolute_path = os.path.join(root, file_name)
                relative_path = absolute_path.replace(parent_folder + '/', '')
                zip_file.write(absolute_path, relative_path)
    except IOError:
        sys.exit(1)
    finally:
        zip_file.close()

    shutil.rmtree(folder_path)


def clip_image_to_extent(extent, source_image_path, output_image_path):
    def split_path(source_path):
        file_dir = os.path.split(source_path)[0]
        file_name = os.path.split(source_path)[1]
        file_extension = os.path.splitext(file_name)[1]
        file_name = os.path.splitext(file_name)[0]

        print(file_name)

        return file_dir, file_name, file_extension

    def pixel_to_world(geotransform_matrix, column, row):
        c = geotransform_matrix[0]
        a = geotransform_matrix[1]
        b = geotransform_matrix[2]
        f = geotransform_matrix[3]
        d = geotransform_matrix[4]
        e = geotransform_matrix[5]

        xp = a * column + b * row + a * 0.5 + b * 0.5 + c
        yp = d * column + e * row + d * 0.5 + e * 0.5 + f

        return xp, yp

    source_file_dir, source_file_name, source_file_extension = split_path(source_image_path)

    wkt_projection = 'GEOGCS["WGS 84",' \
                     'DATUM["WGS_1984",' \
                     'SPHEROID["WGS 84",6378137,298.257223563,' \
                     'AUTHORITY["EPSG","7030"]],' \
                     'AUTHORITY["EPSG","6326"]],' \
                     'PRIMEM["Greenwich",0,' \
                     'AUTHORITY["EPSG","8901"]],' \
                     'UNIT["degree",0.01745329251994328,' \
                     'AUTHORITY["EPSG","9122"]],' \
                     'AUTHORITY["EPSG","4326"]]'

    if source_file_extension == '.tif' or source_file_extension == '.tiff':
        source_image = gdal.Open(source_image_path)

        gcps = source_image.GetGCPs()
        gcp_x = []
        gcp_y = []
        for gcp, val in enumerate(gcps):
            gcp_x.append(gcps[gcp].GCPX)
            gcp_y.append(gcps[gcp].GCPY)
        min_source_x = min(gcp_x)
        max_source_x = max(gcp_x)
        min_source_y = min(gcp_y)
        max_source_y = max(gcp_y)

        error_threshold = 0.125
        resampling = gdal.GRA_NearestNeighbour
        middle_image = gdal.AutoCreateWarpedVRT(source_image, None, wkt_projection, resampling, error_threshold)

        source_cols = middle_image.RasterXSize
        source_rows = middle_image.RasterYSize

        geotransform = [min_source_x, (max_source_x - min_source_x) / source_cols, 0,
                        max_source_y, 0, (max_source_y - min_source_y) / source_rows * (-1)]

        source_image = None

        pixel_size_source_x = geotransform[1]
        pixel_size_source_y = geotransform[5]

        min_output_i = int((extent['min_x'] - min_source_x) / pixel_size_source_x)
        max_output_j = int((extent['min_y'] - max_source_y) / pixel_size_source_y)
        max_output_i = int((extent['max_x'] - min_source_x) / pixel_size_source_x)
        min_output_j = int((extent['max_y'] - max_source_y) / pixel_size_source_y)

        output_cols = max_output_i - min_output_i + 1
        output_rows = max_output_j - min_output_j + 1

        middle_array = middle_image.ReadAsArray(min_output_i, min_output_j, output_cols, output_rows)

        #################################################

        output_gcps = []

        i, j = pixel_to_world(geotransform, max_output_i, min_output_j)
        output_gcps.append(gdal.GCP(i, j, 0.0, output_cols - 1, 0.0))  # BR

        i, j = pixel_to_world(geotransform, min_output_i, min_output_j)
        output_gcps.append(gdal.GCP(i, j, 0.0, 0.0, 0.0))  # UL

        i, j = pixel_to_world(geotransform, min_output_i, max_output_j)
        output_gcps.append(gdal.GCP(i, j, 0.0, 0.0, output_rows - 1))  # BL

        i, j = pixel_to_world(geotransform, max_output_i, max_output_j)
        output_gcps.append(gdal.GCP(i, j, 0.0, output_cols - 1, output_rows - 1))  # UR

        #################################################

        # min_output_x = min_source_x + min_output_i * pixel_size_source_x
        # max_output_y = max_source_y + min_output_j * pixel_size_source_y
        # new_transform = (min_output_x, pixel_size_source_x, 0.0, max_output_y, 0.0, pixel_size_source_y)

        output_image = gdal.GetDriverByName('GTiff').Create(output_image_path, output_cols, output_rows, bands=1,
                                                            eType=gdal.GDT_Byte)

        output_image.SetProjection(wkt_projection)
        output_image.SetGCPs(output_gcps, wkt_projection)

        output_image.GetRasterBand(1).WriteArray(middle_array)

        output_image = None
        middle_image = None

    elif source_file_extension == '.jp2':
        source_spatial_reference = osr.SpatialReference()
        source_spatial_reference.ImportFromWkt(wkt_projection)

        source_image = gdal.Open(source_image_path)
        utm_projection = source_image.GetProjection()

        output_spatial_reference = osr.SpatialReference()
        output_spatial_reference.ImportFromWkt(utm_projection)

        geotransform = source_image.GetGeoTransform()

        error_threshold = 0.125
        resampling = gdal.GRA_NearestNeighbour
        dataset_middle = gdal.AutoCreateWarpedVRT(source_image, None, utm_projection, resampling, error_threshold)

        cols = dataset_middle.RasterXSize
        rows = dataset_middle.RasterYSize

        #################################################

        min_source_x = geotransform[0]
        max_source_y = geotransform[3]
        pixel_size_source_x = geotransform[1]
        pixel_size_source_y = geotransform[5]

        transform = osr.CoordinateTransformation(source_spatial_reference, output_spatial_reference)

        min_output_x = transform.TransformPoint(extent['min_x'], extent['min_y'])[0]
        max_output_y = transform.TransformPoint(extent['min_x'], extent['min_y'])[1]
        max_output_x = transform.TransformPoint(extent['max_x'], extent['max_y'])[0]
        min_output_y = transform.TransformPoint(extent['max_x'], extent['max_y'])[1]

        # i1j1 = transform.TransformPoint(extent['min_x'], extent['min_y'])
        # i2j2 = transform.TransformPoint(extent['max_x'], extent['max_y'])

        # min_output_i = int((i1j1[0] - min_source_x) / pixel_size_source_x)
        # max_output_j = int((i1j1[1] - max_source_y) / pixel_size_source_y)
        # max_output_i = int((i2j2[0] - min_source_x) / pixel_size_source_x)
        # min_output_j = int((i2j2[1] - max_source_y) / pixel_size_source_y)

        min_output_i = int((min_output_x - min_source_x) / pixel_size_source_x)
        max_output_j = int((max_output_y - max_source_y) / pixel_size_source_y)
        max_output_i = int((max_output_x - min_source_x) / pixel_size_source_x)
        min_output_j = int((min_output_y - max_source_y) / pixel_size_source_y)

        output_cols = max_output_i - min_output_i + 1
        output_rows = max_output_j - min_output_j + 1

        source_array = source_image.ReadAsArray(min_output_i, min_output_j, output_cols, output_rows)

        if numpy.any(source_array):
            min_output_x = min_source_x + min_output_i * pixel_size_source_x
            max_output_y = max_source_y + min_output_j * pixel_size_source_y

            new_transform = (min_output_x, pixel_size_source_x, 0.0, max_output_y, 0.0, pixel_size_source_y)

            output_image = gdal.GetDriverByName('GTiff').Create(output_image_path, output_cols, output_rows, bands=1,
                                                                eType=gdal.GDT_Int16)

            output_image.SetProjection(utm_projection)
            output_image.SetGeoTransform(new_transform)

            if source_array.ndim < 3:
                output_image.GetRasterBand(1).WriteArray(source_array)

        output_image = None
        dataset_middle = None
        source_image = None


def iterate_product(product, order):
    """
    Iterates over downloaded product content and calls the clip function for each imagery file (*.tiff or *.jp2).

    :param obj product: django.models Product object
    :param obj order: django.models Order object
    """

    if product.satellite[:2] == 'S1':
        # If it's a Sentinel-1 product iterates over *.tiff files in the product_title.safe/measurement directory
        if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title)):
            os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title))

        for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'measurement')):
            if image.endswith('.tiff'):

                filename = os.path.splitext(image)[0]
                file_attributes = filename.split('-')
                file_layer = file_attributes[3]

                if file_layer in order.layers:
                    source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                     'measurement', image)
                    output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title, image)

                    # clip_image_tiff(order.extent(), source_image_path, output_image_path)
                    clip_image_to_extent(order.extent(), source_image_path, output_image_path)

    elif product.satellite[:2] == 'S2':
        subfolder = os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE'))
        # TODO: product.product_type ???
        if product.title[4:10] == 'MSIL2A':
            for sub in subfolder:

                subsubfolder = os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                       'GRANULE', sub, 'IMG_DATA'))

                for subsub in subsubfolder:

                    # if not os.path.exists(os.path.join(ORDERS_DIR, product.id, product.title, sub, subsub)):
                    #     os.makedirs(os.path.join(ORDERS_DIR, product.id, product.title, sub, subsub))

                    if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, subsub)):
                        os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, subsub))

                    for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                         'GRANULE', sub, 'IMG_DATA', subsub)):
                        if image.endswith('.jp2'):
                            filename = os.path.splitext(image)[0]
                            file_attributes = filename.split('_')
                            file_layer = file_attributes[-2] + '_' + file_attributes[-1]

                            if file_layer in order.layers:
                                source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                                 'GRANULE', sub, 'IMG_DATA', subsub, image)
                                output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title,
                                                                 sub, subsub, image)

                                # clip_image_jp2(order.extent(), source_image_path, output_image_path)
                                clip_image_to_extent(order.extent(), source_image_path, output_image_path)
        else:
            for sub in subfolder:
                if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub)):
                    os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub))

                for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                     'GRANULE', sub, 'IMG_DATA')):
                    if image.endswith('.jp2'):
                        filename = os.path.splitext(image)[0]
                        file_attributes = filename.split('_')
                        file_layer = file_attributes[-2] + '_' + file_attributes[-1]
                        if file_layer in order.layers:
                            source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE',
                                                             'GRANULE', sub, 'IMG_DATA', image)
                            output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, image)

                            # clip_image_jp2(order.extent(), source_image_path, output_image_path)
                            clip_image_to_extent(order.extent(), source_image_path, output_image_path)


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
        # download product (if not already downloaded)
        if not os.path.isfile(os.path.join(TEMP_DIR, p.id + '.zip')):
            print('Product is being downloaded')
            download_product(p.id)

        if not os.path.exists(os.path.join(TEMP_DIR, p. id, p.title + '.SAFE')):
            print('Product is being extracted')
            unzip_product(p.id)

        # clip product
        iterate_product(p, order)

    # zip order
    zip_order(order_id)

    # set order status to COMPLETE
    order.completed_date_time = timezone.now()
    order.status = 2
    order.save()
