from __future__ import absolute_import, unicode_literals
from celery import shared_task

import os
import sys
import shutil
import zipfile

from django.utils import timezone
from django.conf import settings

import xml.etree.ElementTree
import requests
from datetime import datetime
from datetime import timedelta
import time
import json

import numpy as np

from osgeo import gdal, gdalnumeric, ogr, osr
from PIL import Image, ImageDraw
from django.contrib.gis.geos import GEOSGeometry
from .models import Product

BASE_DIR = settings.BASE_DIR
TEMP_DIR = os.path.join(BASE_DIR, 'data/temp')
ORDERS_DIR = os.path.join(BASE_DIR, 'data/orders')
IMAGERY_DIR = os.path.join(BASE_DIR, 'data/imagery')
SHP_PATH = os.path.join(BASE_DIR, 'data/shp/PL.shp')

@shared_task
def update_database():
    def get_xml(url):
        passwords = json.load(open(os.path.join(BASE_DIR, 'passwords.json')))

        r = requests.get(url, auth=(passwords['scihub']['user'], passwords['scihub']['password']))
        e = xml.etree.ElementTree.fromstring(r.content)
        return e

    def get_last_update():
        f = open('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/search/update_database.log', 'r')
        log = f.readlines()
        last_line = log[-1]

        print("Got last product time:", last_line[:23])

        last_update_time = datetime.strptime(last_line[:23], '%Y-%m-%d %H:%M:%S.%f')
        last_update_status = last_line[-3:]
        last_update_time_difference = datetime.now() - last_update_time
        f.close()

        return {'lastUpdateTime': last_update_time,
                'lastUpdateStatus': last_update_status,
                'lastUpdateTimeDifference':
                    (last_update_time_difference.microseconds +
                     (last_update_time_difference.seconds +
                      last_update_time_difference.days * 24 * 3600) * 10 ** 6) / 10 ** 6
                }

    def write_update_time(status, last_product_time):
        f = open('/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/search/update_database.log', 'a')
        last_product_time = last_product_time + timedelta(milliseconds=1)
        f.write(last_product_time.__format__('%Y-%m-%d %H:%M:%S.%f')
                + ' ' + status + '\n')
        f.close()
        print("Writing last product time:",
              last_product_time.__format__('%Y-%m-%d %H:%M:%S.%f'))

    def size_to_bytes(size):
        if size[-2:] == 'GB':
            return str(int((float(size[:-3]) * (10 ** 9))))
        elif size[-2:] == 'MB':
            return str(int((float(size[:-3]) * (10 ** 6))))
        else:
            return None

    def get_product(position):
        product = {}

        for attribute in position:
            if attribute.tag == namespace + 'title':
                satellite = attribute.text[:3]
                product['title'] = attribute.text
                product['satellite'] = satellite
            elif attribute.tag == namespace + 'id':
                product['id'] = attribute.text
            elif attribute.tag == namespace + 'title':
                product['title'] = attribute.text
            elif attribute.attrib and ('name' in attribute.attrib):
                if attribute.attrib['name'] == 'instrumentshortname':
                    product['instrument'] = attribute.text
                elif attribute.attrib['name'] == 'sensoroperationalmode':
                    product['mode'] = attribute.text
                elif attribute.attrib['name'] == 'ingestiondate':
                    try:
                        product['ingestiondate'] = datetime.strptime(attribute.text, '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        product['ingestiondate'] = datetime.strptime(attribute.text, '%Y-%m-%dT%H:%M:%SZ')
                elif attribute.attrib['name'] == 'endposition':
                    try:
                        product['sensingdate'] = datetime.strptime(attribute.text, '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        product['sensingdate'] = datetime.strptime(attribute.text, '%Y-%m-%dT%H:%M:%SZ')
                elif attribute.attrib['name'] == 'footprint':
                    feature['geometry']['coordinates'] = attribute.text
                elif attribute.attrib['name'] == 'orbitnumber':
                    product['orbitnumber'] = attribute.text
                elif attribute.attrib['name'] == 'relativeorbitnumber':
                    product['relativeorbitnumber'] = attribute.text
                elif attribute.attrib['name'] == 'orbitdirection':
                    product['orbitdirection'] = attribute.text
                elif attribute.attrib['name'] == 'size':
                    product['size'] = attribute.text
                elif attribute.attrib['name'] == 'producttype':
                    product['producttype'] = attribute.text
                elif attribute.attrib['name'] == 'polarisationmode' and satellite[:2] == 'S1':
                    product['polarisationmode'] = attribute.text
                elif attribute.attrib['name'] == 'productclass' and satellite[:2] == 'S1':
                    product['productclass'] = attribute.text
                elif attribute.attrib['name'] == 'cloudcoverpercentage' and satellite[:2] == 'S2':
                    product['cloudcover'] = attribute.text
                elif attribute.attrib['name'] == 'processingbaseline' and satellite[:2] == 'S2':
                    product['processingbaseline'] = attribute.text
                elif attribute.attrib['name'] == 'processinglevel' and satellite[:2] == 'S2':
                    product['processinglevel'] = attribute.text

        if 'cloudcover' not in product:
            product['cloudcover'] = None

        if 'polarisationmode' not in product:
            product['polarisationmode'] = None
            product['mode'] = 'MSIL'

        if product['mode'] == 'Earth Observation':
            product['mode'] = 'EO'

        if len(product['producttype']) > 8:
            product['producttype'] = product['producttype'][:8]

        product['isdownloaded'] = False
        return product

    last_update = get_last_update()

    last_product_time = last_update

    while last_update['lastUpdateTimeDifference'] > 3600 * 8:

        query_uri = 'https://scihub.copernicus.eu/apihub/search?q=ingestiondate:[' + last_update[
            'lastUpdateTime'].isoformat() + 'Z%20TO%20NOW]%20AND%20footprint:%22Intersects(' \
                                            'POLYGON((14.17%2054.14,18.19%2055.00,' \
                                            '23.69%2054.35,24.26%2050.50,' \
                                            '23.00%20 49.00,19.00%20 49.18,' \
                                            '14.68%2050.73,14.02%2052.84,' \
                                            '14.17%2054.14)))%22' \
                                            '&orderby=ingestiondate%20asc&rows=100'

        xmldoc = get_xml(query_uri)

        namespace = '{http://www.w3.org/2005/Atom}'

        for entry in xmldoc.iter(tag=namespace + 'entry'):
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Linestring',
                    'coordinates': ''
                }
            }

            feature['properties'] = get_product(entry)

            last_product_time = feature['properties']['ingestiondate']

            print(feature['properties']['id'])
            print(feature['properties']['satellite'])
            print(feature['properties']['producttype'])
            print(feature['properties']['ingestiondate'].__format__('%Y-%m-%d %H:%M:%S.%f'))

            new_product = Product.objects.create(
                id=feature['properties']['id'],
                title=feature['properties']['title'],
                ingestion_date=feature['properties']['ingestiondate'],
                satellite=feature['properties']['satellite'],
                mode=feature['properties']['mode'],
                orbit_direction=feature['properties']['orbitdirection'],
                cloud_cover=feature['properties']['cloudcover'],
                polarisation_mode=feature['properties']['polarisationmode'],
                product_type=feature['properties']['producttype'],
                relative_orbit_number=feature['properties']['relativeorbitnumber'],
                size=size_to_bytes(feature['properties']['size']),
                coordinates=GEOSGeometry(feature['geometry']['coordinates'], srid=4326),
                sensing_date=feature['properties']['sensingdate'],
                is_downloaded=feature['properties']['isdownloaded'],
            )

            new_product.save()

        write_update_time('200', last_product_time)
        print('Waiting 15 secs')
        time.sleep(15)

        last_update = get_last_update()
    else:
        print("DB update complete")

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

def clip_image_tiff(id, title, filename, sourceImagePath, outputImagePath):
    def imageToArray(i):
        """
        Converts a Python Imaging Library array to a
        gdalnumeric image.
        """
        a = gdalnumeric.fromstring(i.tobytes(), 'b')
        a.shape = i.im.size[1], i.im.size[0]
        return a

    def arrayToImage(a):
        """
        Converts a gdalnumeric array to a
        Python Imaging Library Image.
        """
        i = Image.fromstring('L', (a.shape[1], a.shape[0]),
                             (a.astype('b')).tostring())
        return i

    def world2Pixel(geoMatrix, x, y):
        """
        Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
        the pixel location of a geospatial coordinate
        """

        ulX = geoMatrix[0]
        ulY = geoMatrix[3]
        xDist = geoMatrix[1]
        yDist = geoMatrix[5]
        rtnX = geoMatrix[2]
        rtnY = geoMatrix[4]
        pixel = int((x - ulX) / xDist)
        line = int((y - ulY) / yDist)
        return (pixel, line)

    def getGeometryExtent(points):
        ## Convert the layer extent to image pixel coordinates V2?
        minX = min(points, key=lambda x: x[0])[0]
        maxX = max(points, key=lambda x: x[0])[0]
        minY = min(points, key=lambda x: x[1])[1]
        maxY = max(points, key=lambda x: x[1])[1]
        return minX, maxX, minY, maxY

    def GetPixelCoords(col, row):
        xp = a * col + b * row + a * 0.5 + b * 0.5 + c
        yp = d * col + e * row + d * 0.5 + e * 0.5 + f
        return (xp, yp)

    wkt_projection = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    SOURCE_IMAGE_PATH = os.path.join(sourceImagePath, filename + '.tiff')
    FINAL_IMAGE_PATH = os.path.join(outputImagePath, filename + '.tiff')

    source_image = gdal.Open(SOURCE_IMAGE_PATH)

    gcps = source_image.GetGCPs()

    gcp_x = []
    gcp_y = []

    for a, val in enumerate(gcps):
        gcp_x.append(gcps[a].GCPX)
        gcp_y.append(gcps[a].GCPY)

    geotransform = {'minX': min(gcp_x), 'maxX': max(gcp_x), 'minY': min(gcp_y), 'maxY': max(gcp_y)}

    error_threshold = 0.125
    resampling = gdal.GRA_NearestNeighbour
    middle_image = gdal.AutoCreateWarpedVRT(source_image, None, wkt_projection, resampling, error_threshold)

    source_image = None

    cols = middle_image.RasterXSize
    rows = middle_image.RasterYSize

    geotransform = [geotransform['minX'], (geotransform['maxX'] - geotransform['minX']) / cols, 0,
                    geotransform['maxY'], 0, (geotransform['maxY'] - geotransform['minY']) / rows * (-1)]

    c, a, b, f, d, e = middle_image.GetGeoTransform()

    xOrigin = geotransform[0]
    yOrigin = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]

    sourceMaxRasterX = xOrigin + (cols * pixelWidth)
    sourceMinRasterY = yOrigin + (rows * pixelHeight)

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    shapefile = ogr.Open(SHP_PATH)
    lyr = shapefile.GetLayer("PL")
    poly = lyr.GetNextFeature()
    cutterGeometry = poly.GetGeometryRef()

    # str(xOrigin) + ' ' + str(yOrigin) + ',' + str(sourceMaxRasterX), str(yOrigin),str(sourceMaxRasterX), str(sourceMinRasterY),str(xOrigin), str(sourceMinRasterY),str(xOrigin), str(yOrigin)

    image_WKT = 'POLYGON ((' + str(xOrigin) + ' ' + str(yOrigin) + ',' + str(sourceMaxRasterX) + ' ' + str(yOrigin) + ',' + str(sourceMaxRasterX) + ' ' + str(sourceMinRasterY) + ',' + str(xOrigin) + ' ' + str(sourceMinRasterY) + ',' + str(xOrigin) + ' ' + str(yOrigin) + '))'

    rasterGeometry = ogr.CreateGeometryFromWkt(image_WKT)

    shapei = cutterGeometry.Intersection(rasterGeometry)

    pts = shapei.GetGeometryRef(0)
    points = []
    for p in range(pts.GetPointCount()):
        points.append((pts.GetX(p), pts.GetY(p)))
    minX, maxX, minY, maxY = getGeometryExtent(points)

    ulX, ulY = world2Pixel(geotransform, minX, maxY)
    lrX, lrY = world2Pixel(geotransform, maxX, minY)

    print(ulX, ulY, lrX, lrY)

    # srcArray = gdalnumeric.LoadFile(srcImage_path)

    # np.array(ds.GetRasterBand(1).ReadAsArray())

    #middle_array = gdalnumeric.LoadFile(srcImage_path)

    middle_array = np.array(middle_image.GetRasterBand(1).ReadAsArray())


    # geoTrans = srcImage.GetGeoTransform() ???
    # geoTrans = middle_image.GetGeoTransform()

    if (ulX < 0):
        ulX = 0
    if (ulY < 0):
        ulY = 0
    if (lrX > cols):
        lrX = cols
    if (lrY > rows):
        lrY = rows

    pxWidth = int(lrX - ulX)
    pxHeight = int(lrY - ulY)

    clip = middle_array[ulY:lrY, ulX:lrX]

    geoTrans = list(geotransform)
    geoTrans[0] = minX
    geoTrans[3] = maxY

    pixels = []

    for p in points:
        pixels.append(world2Pixel(geoTrans, p[0], p[1]))

    rasterPoly = Image.new("L", (pxWidth, pxHeight), 1)
    rasterize = ImageDraw.Draw(rasterPoly)
    rasterize.polygon(pixels, 0)
    mask = imageToArray(rasterPoly)

    try:
        clip = gdalnumeric.choose(mask, (clip, 0)).astype(gdalnumeric.uint16)
    except ValueError:
        clip = mask

    driver = gdal.GetDriverByName('GTiff')
    final_image = driver.Create(FINAL_IMAGE_PATH, pxWidth, pxHeight, 1, gdal.GDT_UInt16)
    final_image.GetRasterBand(1).WriteArray(clip)

    proj = middle_image.GetProjection()
    final_image.SetGeoTransform(geoTrans)
    final_image.SetProjection(proj)
    final_image.FlushCache()
    final_image = None

def clip_image_jp2(filename, sourceImagePath, outputImagePath):
    def imageToArray(i):
        """
        Converts a Python Imaging Library array to a
        gdalnumeric image.
        """
        a = gdalnumeric.fromstring(i.tobytes(), 'b')
        a.shape = i.im.size[1], i.im.size[0]
        return a

    def arrayToImage(a):
        """
        Converts a gdalnumeric array to a
        Python Imaging Library Image.
        """
        i = Image.fromstring('L', (a.shape[1], a.shape[0]),
                             (a.astype('b')).tostring())
        return i

    def world2Pixel(geoMatrix, x, y):
        """
        Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
        the pixel location of a geospatial coordinate
        """

        ulX = geoMatrix[0]
        ulY = geoMatrix[3]
        xDist = geoMatrix[1]
        yDist = geoMatrix[5]
        rtnX = geoMatrix[2]
        rtnY = geoMatrix[4]
        pixel = int((x - ulX) / xDist)
        line = int((y - ulY) / yDist)
        return (pixel, line)

    def getGeometryExtent(points):
        ## Convert the layer extent to image pixel coordinates V2?
        minX = min(points, key=lambda x: x[0])[0]
        maxX = max(points, key=lambda x: x[0])[0]
        minY = min(points, key=lambda x: x[1])[1]
        maxY = max(points, key=lambda x: x[1])[1]
        return minX, maxX, minY, maxY

    SOURCE_IMAGE_PATH = os.path.join(sourceImagePath, filename + '.jp2')
    FINAL_IMAGE_PATH = os.path.join(outputImagePath, filename + '.jp2')

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    srcImage = gdal.Open(os.path.join(sourceImagePath, filename + '.jp2'))
    gdal.Warp(os.path.join(sourceImagePath, filename + '_WGS84.jp2'), srcImage, dstSRS='EPSG:4326')

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    srcImage = gdal.Open(os.path.join(sourceImagePath, filename + '_WGS84.jp2'))
    srcArray = gdalnumeric.LoadFile(os.path.join(sourceImagePath, filename + '_WGS84.jp2'))
    geoTrans = srcImage.GetGeoTransform()

    sourceMinRasterX = geoTrans[0]
    xPixelSize = geoTrans[1]
    sourceMaxRasterY = geoTrans[3]
    yPixelSize = geoTrans[5]

    sourceRasterHeight = srcImage.RasterYSize
    sourceRasterWidth = srcImage.RasterXSize

    sourceMaxRasterX = sourceMinRasterX + (sourceRasterWidth * xPixelSize)
    sourceMinRasterY = sourceMaxRasterY + (sourceRasterHeight * yPixelSize)

    # Create an OGR layer from a boundary shapefile
    shapefile = ogr.Open(SHP_PATH)
    lyr = shapefile.GetLayer("PL")
    poly = lyr.GetNextFeature()
    cutterGeometry = poly.GetGeometryRef()

    rasterWKT = "POLYGON ((%s %s, %s %s, %s %s, %s %s, %s %s))" % (
    str(sourceMinRasterX), str(sourceMaxRasterY), str(sourceMaxRasterX), str(sourceMaxRasterY), str(sourceMaxRasterX),
    str(sourceMinRasterY), str(sourceMinRasterX), str(sourceMinRasterY), str(sourceMinRasterX), str(sourceMaxRasterY))

    rasterGeometry = ogr.CreateGeometryFromWkt(rasterWKT)

    shapei = cutterGeometry.Intersection(rasterGeometry)

    pts = shapei.GetGeometryRef(0)
    points = []
    for p in range(pts.GetPointCount()):
        points.append((pts.GetX(p), pts.GetY(p)))
    minX, maxX, minY, maxY = getGeometryExtent(points)

    ulX, ulY = world2Pixel(geoTrans, minX, maxY)
    lrX, lrY = world2Pixel(geoTrans, maxX, minY)

    if (ulX < 0):
        ulX = 0
    if (ulY < 0):
        ulY = 0
    if (lrX > sourceRasterWidth):
        lrX = sourceRasterWidth
    if (lrY > sourceRasterHeight):
        lrY = sourceRasterHeight

    pxWidth = int(lrX - ulX)
    pxHeight = int(lrY - ulY)

    clip = srcArray[ulY:lrY, ulX:lrX]

    # Create a new geomatrix for the image
    geoTrans = list(geoTrans)
    geoTrans[0] = minX
    geoTrans[3] = maxY

    pixels = []

    for p in points:
        pixels.append(world2Pixel(geoTrans, p[0], p[1]))

    rasterPoly = Image.new("L", (pxWidth, pxHeight), 1)
    rasterize = ImageDraw.Draw(rasterPoly)
    rasterize.polygon(pixels, 0)
    mask = imageToArray(rasterPoly)

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    try:
        clip = gdalnumeric.choose(mask, (clip, 0)).astype(gdalnumeric.uint16)
    except ValueError:
        clip = mask

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    # pxWidth = lrX - ulX
    # pxHeight = lrY - ulY

    FINAL_IMAGE_PATH = os.path.join(outputImagePath, filename + '.tiff')

    print(filename)

    driver = gdal.GetDriverByName('GTiff')
    final_image = driver.Create(FINAL_IMAGE_PATH, pxWidth, pxHeight, 1, gdal.GDT_UInt16)
    final_image.GetRasterBand(1).WriteArray(clip)

    proj = srcImage.GetProjection()
    final_image.SetGeoTransform(geoTrans)
    final_image.SetProjection(proj)
    final_image.FlushCache()
    final_image = None

def zip_product(id, title):
    """
    Zips a requested order to the /ORDERS_PATH/order_id.zip file
    :param str order_id: Order ID
    """

    folder_path = os.path.join(TEMP_DIR, title)
    output_path = os.path.join(IMAGERY_DIR, id + '.zip')

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

def iterate_product(id, title, satellite):
    """
    Iterates over downloaded product content and calls the clip function for each imagery file (*.tiff or *.jp2).

    :param obj product: django.models Product object
    :param obj order: django.models Order object
    """

    if (satellite[:2] == 'S1'):
        if not os.path.exists(os.path.join(TEMP_DIR, title)):
            os.makedirs(os.path.join(TEMP_DIR, title))

        for image in os.listdir(os.path.join(TEMP_DIR, id, title + '.SAFE', 'measurement')):
            if image.endswith('.tiff'):
                source_image_path = os.path.join(TEMP_DIR, id, title + '.SAFE', 'measurement')
                output_image_path = os.path.join(TEMP_DIR, title)

                print(source_image_path)
                print(output_image_path)
                print(image)

                clip_image_tiff(id, title, image[:-5], source_image_path, output_image_path)

        zip_product(id, title)

    elif (satellite[:2] == 'S2'):
        subfolder = os.listdir(os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE'))
        if title[4:10] == 'MSIL2A':
            for sub in subfolder:

                subsubfolder = os.listdir(os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE', sub, 'IMG_DATA'))

                for subsub in subsubfolder:

                    if not os.path.exists(os.path.join(TEMP_DIR, title, sub, subsub)):
                        os.makedirs(os.path.join(TEMP_DIR, title, sub, subsub))

                    for image in os.listdir(os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE', sub, 'IMG_DATA', subsub)):
                        if image.endswith('.jp2') and image[-11:-9] != 'SCL':

                            # orders/40/S2A_MSIL2A_20180529T101031_N0208_R022_T33UVS_20180529T112942/L2A_T33UVS_A015320_20180529T101225/R20m/T33UVS_20180529T101031_B07_20m/.tiff

                            source_image_path = os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE', sub, 'IMG_DATA', subsub)
                            output_image_path = os.path.join(TEMP_DIR, title, sub, subsub)

                            print(source_image_path)
                            print(output_image_path)

                            clip_image_jp2(image[:-4], source_image_path, output_image_path)



        else:
            for sub in subfolder:
                if not os.path.exists(os.path.join(TEMP_DIR, title, sub)):
                    os.makedirs(os.path.join(TEMP_DIR, title, sub))

                for image in os.listdir(os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE', sub, 'IMG_DATA')):
                    if image.endswith('.jp2'):
                        source_image_path = os.path.join(TEMP_DIR, id, title + '.SAFE', 'GRANULE', sub, 'IMG_DATA')
                        output_image_path = os.path.join(TEMP_DIR, title, sub)
                        clip_image_jp2(image[:-4], source_image_path, output_image_path)

        zip_product(id, title)


@shared_task
def rolling_archive():
    # time_range_end = timezone.now()
    # time_range_start = time_range_end - timedelta(days=14)

    time_range_end = timezone.now()
    time_range_start = time_range_end - timedelta(hours=6)

    expired_products = Product.objects.filter(is_downloaded=True, ingestion_date__lt=time_range_start)
    print(expired_products)

    for product in expired_products:
        shutil.rmtree(os.path.join(BASE_DIR, product.id + '.zip'))
        product.is_downloaded = False
        product.save()

    print('deleted expired products')

    fresh_products = Product.objects.filter(is_downloaded=False, ingestion_date__gte=time_range_start, product_type='GRD')
    print(fresh_products)

    for product in fresh_products:
        download_product(product.id)
        unzip_product(product.id)

        shutil.rmtree(os.path.join(TEMP_DIR, product.id + '.zip'))

        iterate_product(product.id, product.title, product.satellite)

        product.is_downloaded = True
        product.save()
