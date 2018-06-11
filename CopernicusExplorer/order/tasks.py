from __future__ import absolute_import, unicode_literals
from celery import shared_task

import sys
import os
from django.utils import timezone
import json
import requests
import zipfile
import shutil
import numpy
from osgeo import ogr, osr, gdal

#sys.path.append('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/modules')

from django.conf import settings

# os.path.join(BASE_DIR, ...)

BASE_DIR = settings.BASE_DIR
TEMP_DIR = os.path.join(BASE_DIR, 'data/temp')
ORDERS_DIR = os.path.join(BASE_DIR, 'data/orders')
IMAGERY_DIR = os.path.join(BASE_DIR, 'data/imagery')

from .models import Order, ProductOrder, Product

def download_product(id):
    """
    Downloads a Sentinel product from ESA archive and writes it to the hard drive
    :param str id: Product ID
    """

    url = "https://scihub.copernicus.eu/dhus/odata/v1/Products('" + id + "')/$value"

    passwords = json.load(open(os.path.join(BASE_DIR, 'passwords.json')))

    username = passwords['scihub']['user']
    password = passwords['scihub']['password']

    r = requests.get(url, auth=(username, password), stream=True)
    if r.status_code == 200:
        with open(os.path.join(TEMP_DIR, id + '.zip'), 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

    sys.stdout.flush()


def unzip_product(id):
    """
    Unzips the product to /DOWNLOAD_PATH/id/
    :param str id: Product ID
    """

    zip_ref = zipfile.ZipFile(os.path.join(TEMP_DIR, id + '.zip'), 'r')
    zip_ref.extractall(os.path.join(TEMP_DIR, id))
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
        zipFile = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)
        for root, folders, files in contents:
            for folder_name in folders:
                absolute_path = os.path.join(root, folder_name)
                relative_path = absolute_path.replace(parent_folder + '/', '')
                zipFile.write(absolute_path, relative_path)

            for file_name in files:
                absolute_path = os.path.join(root, file_name)
                relative_path = absolute_path.replace(parent_folder + '/', '')
                zipFile.write(absolute_path, relative_path)
    except IOError:
        sys.exit(1)
    finally:
        zipFile.close()

    shutil.rmtree(folder_path)


def clip_image_tiff(extent, source_image_path, output_image_path):
    """
    Clips a GeoTIFF image to defined bounding box and saves it as a *.tiff file

    :param dict extent:
    :param str source_image_path:
    :param str output_image_path:
    """

    WKT_Projection = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

    dataset = gdal.Open(source_image_path)
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize

    #################################################

    GCPs = dataset.GetGCPs()

    GCPX = []
    GCPY = []

    for a, val in enumerate(GCPs):
        GCPX.append(GCPs[a].GCPX)
        GCPY.append(GCPs[a].GCPY)

    geotransform = {'minX': min(GCPX), 'maxX': max(GCPX), 'minY': min(GCPY), 'maxY': max(GCPY)}

    #################################################

    error_threshold = 0.125
    resampling = gdal.GRA_NearestNeighbour
    dataset_middle = gdal.AutoCreateWarpedVRT(dataset, None, WKT_Projection, resampling, error_threshold)

    cols = dataset_middle.RasterXSize
    rows = dataset_middle.RasterYSize

    geotransform = [geotransform['minX'], (geotransform['maxX'] - geotransform['minX']) / cols, 0,
                    geotransform['maxY'], 0, (geotransform['maxY'] - geotransform['minY']) / rows * (-1)]

    dataset = None

    c, a, b, f, d, e = dataset_middle.GetGeoTransform()

    def GetPixelCoords(col, row):
        xp = a * col + b * row + a * 0.5 + b * 0.5 + c
        yp = d * col + e * row + d * 0.5 + e * 0.5 + f
        return (xp, yp)

    #################################################

    xOrigin = geotransform[0]
    yOrigin = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]

    i1 = int((extent['min_x'] - xOrigin) / pixelWidth)
    j1 = int((extent['min_y'] - yOrigin) / pixelHeight)
    i2 = int((extent['max_x'] - xOrigin) / pixelWidth)
    j2 = int((extent['max_y'] - yOrigin) / pixelHeight)

    new_cols = i2 - i1 + 1
    new_rows = j1 - j2 + 1

    data = dataset_middle.ReadAsArray(i1, j2, new_cols, new_rows)

    #################################################

    newGCPs = []
    diff = i2 - i1

    i, j = GetPixelCoords(i2, j2)
    newGCPs.append(gdal.GCP(i, j, 0.0, new_cols - 1, 0.0))  # BR

    i, j = GetPixelCoords(i1, j2)
    newGCPs.append(gdal.GCP(i, j, 0.0, 0.0, 0.0))  # UL

    i, j = GetPixelCoords(i1, j1)
    newGCPs.append(gdal.GCP(i, j, 0.0, 0.0, new_rows - 1))  # BL

    i, j = GetPixelCoords(i2, j1)
    newGCPs.append(gdal.GCP(i, j, 0.0, new_cols - 1, new_rows - 1))  # UR

    #################################################

    newX = xOrigin + i1 * pixelWidth
    newY = yOrigin + j2 * pixelHeight

    new_transform = (newX, pixelWidth, 0.0, newY, 0.0, pixelHeight)

    dst_ds = gdal.GetDriverByName('GTiff').Create(output_image_path, new_cols, new_rows, bands=1, eType=gdal.GDT_Byte)

    dst_ds.SetProjection(WKT_Projection)
    dst_ds.SetGCPs(newGCPs, WKT_Projection)

    dst_ds.GetRasterBand(1).WriteArray(data)

    dst_ds = None
    dataset_middle = None


def clip_image_jp2(extent, source_image_path, output_image_path):
    """
    Clips a JPEG2000 image to defined bounding box and saves it as a *.jp2 file

    :param dict extent:
    :param str source_image_path:
    :param str output_image_path:
    """
    WGS84_projection = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

    in_srs = osr.SpatialReference()
    in_srs.ImportFromWkt(WGS84_projection)

    dataset = gdal.Open(source_image_path)
    UTM_projection = dataset.GetProjection()

    out_srs = osr.SpatialReference()
    out_srs.ImportFromWkt(UTM_projection)

    cols = dataset.RasterXSize
    rows = dataset.RasterYSize

    #################################################

    geotransform = dataset.GetGeoTransform()

    #################################################

    error_threshold = 0.125
    resampling = gdal.GRA_NearestNeighbour
    dataset_middle = gdal.AutoCreateWarpedVRT(dataset, None, UTM_projection, resampling, error_threshold)

    cols = dataset_middle.RasterXSize
    rows = dataset_middle.RasterYSize

    #################################################

    xOrigin = geotransform[0]
    yOrigin = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]

    transform = osr.CoordinateTransformation(in_srs, out_srs)

    i1j1 = transform.TransformPoint(extent['min_x'], extent['min_y'])
    i2j2 = transform.TransformPoint(extent['max_x'], extent['max_y'])

    i1 = int((i1j1[0] - xOrigin) / pixelWidth)
    j1 = int((i1j1[1] - yOrigin) / pixelHeight)
    i2 = int((i2j2[0] - xOrigin) / pixelWidth)
    j2 = int((i2j2[1] - yOrigin) / pixelHeight)

    new_cols = i2 - i1 + 1
    new_rows = j1 - j2 + 1

    data = dataset.ReadAsArray(i1, j2, new_cols, new_rows)

    if numpy.any(data):
        newX = xOrigin + i1 * pixelWidth
        newY = yOrigin + j2 * pixelHeight

        new_transform = (newX, pixelWidth, 0.0, newY, 0.0, pixelHeight)

        dst_ds = gdal.GetDriverByName('GTiff').Create(output_image_path, new_cols, new_rows, bands=1,
                                                      eType=gdal.GDT_Int16)

        dst_ds.SetProjection(UTM_projection)
        dst_ds.SetGeoTransform(new_transform)

        if data.ndim < 3:
            dst_ds.GetRasterBand(1).WriteArray(data)

        dst_ds = None
        dataset_middle = None
        dataset = None

    else:

        dst_ds = None
        dataset_middle = None
        dataset = None


def iterate_product(product, order):
    """
    Iterates over downloaded product content and calls the clip function for each imagery file (*.tiff or *.jp2).

    :param obj product: django.models Product object
    :param obj order: django.models Order object
    """

    # Creates /orders/order_id/product_id directory if it doesn't exist


    if (product.satellite[:2] == 'S1'):
        # If it's a Sentinel-1 product iterates over *.tiff files in the product_title.safe/measurement directory
        if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title)):
            os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title))

        for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'measurement')):
            if image.endswith('.tiff'):
                source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'measurement', image)
                output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title, image)

                print(source_image_path)
                print(output_image_path)
                print(order.extent())

                clip_image_tiff(order.extent(), source_image_path, output_image_path)

    elif (product.satellite[:2] == 'S2'):
        subfolder = os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE'))
        if product.title[4:10] == 'MSIL2A':
            for sub in subfolder:

                subsubfolder = os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE', sub, 'IMG_DATA'))

                for subsub in subsubfolder:

                    # if not os.path.exists(os.path.join(ORDERS_DIR, product.id, product.title, sub, subsub)):
                    #     os.makedirs(os.path.join(ORDERS_DIR, product.id, product.title, sub, subsub))

                    if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, subsub)):
                        os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, subsub))

                    for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE', sub, 'IMG_DATA', subsub)):
                        if image.endswith('.jp2'):

                            # orders/40/S2A_MSIL2A_20180529T101031_N0208_R022_T33UVS_20180529T112942/L2A_T33UVS_A015320_20180529T101225/R20m/T33UVS_20180529T101031_B07_20m/.tiff

                            source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE', sub, 'IMG_DATA', subsub, image)
                            output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, subsub, image[:-4])
                            clip_image_jp2(order.extent(), source_image_path, output_image_path)
        else:
            for sub in subfolder:
                if not os.path.exists(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub)):
                    os.makedirs(os.path.join(ORDERS_DIR, str(order.pk), product.title, sub))

                for image in os.listdir(os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE', sub, 'IMG_DATA')):
                    if image.endswith('.jp2'):
                        source_image_path = os.path.join(TEMP_DIR, product.id, product.title + '.SAFE', 'GRANULE', sub, 'IMG_DATA', image)
                        output_image_path = os.path.join(ORDERS_DIR, str(order.pk), product.title, sub, image[:-4])
                        clip_image_jp2(order.extent(), source_image_path, output_image_path)

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

        if not os.path.isfile(os.path.join(TEMP_DIR, p.id + '.zip')):
            print('Product is being downloaded')
            download_product(p.id)

        if not os.path.exists(os.path.join(TEMP_DIR, p. id, p.title + '.SAFE')):
            print('Product is being extracted')
            unzip_product(p.id)

        #   clip product
        iterate_product(p, order)

    # zip order
    zip_order(order_id)

    # delete order directory


    # set order status to COMPLETE
    order.completed_date_time = timezone.now()
    order.status = 2
    order.save()
