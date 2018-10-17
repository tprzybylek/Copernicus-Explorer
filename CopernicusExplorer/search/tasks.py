from __future__ import absolute_import, unicode_literals
from celery import shared_task

import os
import sys
import shutil
import zipfile
import requests
import json

from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import xml.etree.ElementTree

from datetime import datetime
from datetime import timedelta
import time


import numpy as np

from osgeo import gdal, gdalnumeric, ogr
from PIL import Image, ImageDraw
from django.contrib.gis.geos import GEOSGeometry
from .models import Product, AdministrativeUnit, UpdateLog

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

    def size_to_bytes(size):
        if size[-2:] == 'GB':
            return str(int((float(size[:-3]) * (2 ** 30))))
        elif size[-2:] == 'MB':
            return str(int((float(size[:-3]) * (2 ** 20))))
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
                    feature['geometry']['coordinates'] = GEOSGeometry(attribute.text, srid=4326)
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

                    product['polarisationmode'] = attribute.text.split()

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

        if feature['geometry']['coordinates'].geom_typeid == 6:
            feature['geometry']['coordinates'] = feature['geometry']['coordinates'][0]

        product['isdownloaded'] = False
        return product

    try:
        last_product_time = UpdateLog.objects.latest('log_date').log_date
    except ObjectDoesNotExist:
        last_product_time = settings.ARCHIVE_STARTING_DATE

    last_update_timediff = timezone.now() - last_product_time
    last_update_timediff = last_update_timediff.total_seconds()

    print(last_update_timediff)

    while last_update_timediff > 3600 * 8:
        query_uri = 'https://scihub.copernicus.eu/apihub/search?q=ingestiondate:[' \
                    + last_product_time.replace(tzinfo=None).isoformat() \
                    + 'Z%20TO%20NOW]%20AND%20footprint:%22Intersects(' \
                    'POLYGON((16.0894%2054.3085,16.5261%2054.5959,17.3501%2054.7816,18.3718%2054.8955,' \
                    '18.8964%2054.6261,18.9074%2054.3901,19.6353%2054.4875,21.4315%2054.3613,' \
                    '22.9257%2054.4349,23.5491%2054.1592,23.9172%2053.2356,24.0216%2052.7030,' \
                    '23.2965%2052.2816,23.7414%2052.0997,23.7414%2051.3854,24.1918%2050.8649,' \
                    '24.0875%2050.3629,22.7416%2049.5465,22.9833%2048.9874,22.6428%2048.9838,' \
                    '21.1706%2049.3251,20.0994%2049.1529,19.6984%2049.1781,19.4787%2049.5394,' \
                    '19.1162%2049.3394,18.7316%2049.4966,17.5122%2050.1346,16.6772%2050.0641,' \
                    '16.1279%2050.4085,15.0842%2050.8059,14.7216%2050.8406,14.8315%2051.1724,' \
                    '14.4689%2051.9645,14.5239%2052.5429,14.0185%2052.8027,14.0515%2052.9486,' \
                    '14.2492%2053.2717,14.1174%2053.9754,16.0894%2054.3085)))%22' \
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
                coordinates=feature['geometry']['coordinates'],
                sensing_date=feature['properties']['sensingdate'],
                is_downloaded=feature['properties']['isdownloaded'],
            )

            new_product.save()

        last_product_time = last_product_time + timedelta(milliseconds=1)
        new_status = 1

        new_log_entry = UpdateLog.objects.create(log_date=last_product_time, status=new_status)
        new_log_entry.save()

        print('Waiting 15 secs')
        time.sleep(15)

        last_update_timediff = timezone.now() - last_product_time.replace(tzinfo=timezone.utc)
        last_update_timediff = last_update_timediff.total_seconds()

        print(last_update_timediff)
    else:
        print("DB update complete")


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


def clip_image_to_shape(source_image_path, output_image_path):
    def image_to_array(pil_array):
        """
        Converts a Python Imaging Library (PIL) array to a
        gdalnumeric image.
        """
        gdal_numeric_array = gdalnumeric.fromstring(pil_array.tobytes(), 'b')
        gdal_numeric_array.shape = pil_array.im.size[1], pil_array.im.size[0]
        return gdal_numeric_array

    def split_path(source_path):
        file_dir = os.path.split(source_path)[0]
        file_name = os.path.split(source_path)[1]
        file_extension = os.path.splitext(file_name)[1]
        file_name = os.path.splitext(file_name)[0]

        print(file_name)

        return file_dir, file_name, file_extension

    def get_geometry_extent(polygons):
        xs = []
        ys = []
        for polygon in polygons:
            for point in polygon:
                xs.append(point[0])
                ys.append(point[1])

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        # min_x = min(points, key=lambda x: x[0])[0]
        # max_x = max(points, key=lambda x: x[0])[0]
        # min_y = min(points, key=lambda x: x[1])[1]
        # max_y = max(points, key=lambda x: x[1])[1]
        return min_x, max_x, min_y, max_y

    def world_to_pixel(geotransform_matrix, x, y):
        """
        Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
        the pixel location of a geospatial coordinate
        """

        min_x = geotransform_matrix[0]
        max_y = geotransform_matrix[3]
        pixel_size_x = geotransform_matrix[1]
        pixel_size_y = geotransform_matrix[5]
        # rtnX = geotransform_matrix[2]
        # rtnY = geotransform_matrix[4]
        column = int((x - min_x) / pixel_size_x)
        row = int((y - max_y) / pixel_size_y)
        return column, row

    source_file_dir, source_file_name, source_file_extension = split_path(source_image_path)

    # Output file geographic projection
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

        # (x, y) coordinates refer are geographical coordinates (latitude and longtitude)
        # (i, j) and (cols, rows) are pixel coordinates

        # Read coordinates of ground control points (GCPs) and calculate their extent (min and max x, y values)
        gcps = source_image.GetGCPs()
        gcp_x = []
        gcp_y = []
        for a, val in enumerate(gcps):
            gcp_x.append(gcps[a].GCPX)
            gcp_y.append(gcps[a].GCPY)
        min_source_x = min(gcp_x)
        max_source_x = max(gcp_x)
        min_source_y = min(gcp_y)
        max_source_y = max(gcp_y)

        # A warped virtual raster (middle_raster) needs to be created
        # because the source_raster has no geographical projection.
        # That's why it's being reprojected from None to wkt_projection (None to WGS84).
        error_threshold = 0.125
        resampling = gdal.GRA_NearestNeighbour
        middle_image = gdal.AutoCreateWarpedVRT(source_image, None, wkt_projection, resampling, error_threshold)
        source_image = None

        # Calculate the GeoTransform matrix for the input image
        # geotransform[0]   top left x, minimal x value
        # geotransform[1]   pixel width, pixel size in x dimension
        # geotransform[2]   0
        # geotransform[3]   top left y, maximal y value
        # geotransform[4]   0
        # geotransform[5]   pixel height, pixel size in y dimension, should be negative
        source_cols = middle_image.RasterXSize
        source_rows = middle_image.RasterYSize
        geotransform = [min_source_x, (max_source_x - min_source_x) / source_cols, 0,
                        max_source_y, 0, (max_source_y - min_source_y) / source_rows * (-1)]

        # Calculate the x, y coordinates for a lower right corner of the source_image
        pixel_size_source_x = geotransform[1]
        pixel_size_source_y = geotransform[5]
        max_source_x = min_source_x + (source_cols * pixel_size_source_x)
        min_source_y = max_source_y + (source_rows * pixel_size_source_y)

        # Create a polygon equal to extent of the source_image
        # POLYGON((x1 y1, x2 y2, x3 y3, x4 y4, x1 y1))
        image_wkt = 'POLYGON ((' \
                    + str(min_source_x) + ' ' \
                    + str(max_source_y) + ',' \
                    + str(max_source_x) + ' ' \
                    + str(max_source_y) + ',' \
                    + str(max_source_x) + ' ' \
                    + str(min_source_y) + ',' \
                    + str(min_source_x) + ' ' \
                    + str(min_source_y) + ',' \
                    + str(min_source_x) + ' ' \
                    + str(max_source_y) + '))'
        source_geometry = ogr.CreateGeometryFromWkt(image_wkt)

        # Load a *.shp file and read the single feature containing border
        shapefile = ogr.Open(SHP_PATH)
        shapefile_layer = shapefile.GetLayer("PL")
        shapefile_polygon = shapefile_layer.GetNextFeature()
        border_geometry = shapefile_polygon.GetGeometryRef()

        # Calculate the spatial intersection of the source_image and the border shapefile
        # It's a shape of the output image
        output_geometry = border_geometry.Intersection(source_geometry)
        output_geometry_type = output_geometry.GetGeometryType()
        output_geometry_geom_count = output_geometry.GetGeometryCount()

        # GetGeometryType() == 2: LINEARRING
        # GetGeometryType() == 3: POLYGON
        # GetGeometryType() == 6: MULTIPOLYGON

        # Create a list of (x,y) pairs of output_geometry coordinates
        polygons = []
        if output_geometry_type == 3:
            pts = output_geometry.GetGeometryRef(0)
            polygon = []
            for point in range(pts.GetPointCount()):
                polygon.append((pts.GetX(point), pts.GetY(point)))
            polygons.append(polygon)
        elif output_geometry_type == 6:
            for geom in range(output_geometry_geom_count):
                pts = output_geometry.GetGeometryRef(geom)
                pts = pts.GetGeometryRef(0)
                polygon = []
                for p in range(pts.GetPointCount()):
                    polygon.append((pts.GetX(p), pts.GetY(p)))
                polygons.append(polygon)

        # Calculate the pixel extent of the output_geometry polygon
        min_output_x, max_output_x, min_output_y, max_output_y = get_geometry_extent(polygons)
        min_output_i, max_output_j = world_to_pixel(geotransform, min_output_x, max_output_y)
        max_output_i, min_output_j = world_to_pixel(geotransform, max_output_x, min_output_y)

        # If calculated extent is outside of the source_image array it has to be clipped
        if min_output_i < 0:
            min_output_i = 0
        if max_output_j < 0:
            max_output_j = 0
        if max_output_i > source_cols:
            max_output_i = source_cols
        if min_output_j > source_rows:
            min_output_j = source_rows

        # Width and height of the output_raster in pixels
        output_cols = int(max_output_i - min_output_i)
        output_rows = int(min_output_j - max_output_j)

        # Read the middle image as array and select pixels within calculated range
        middle_array = np.array(middle_image.GetRasterBand(1).ReadAsArray())
        clip = middle_array[max_output_j:min_output_j, min_output_i:max_output_i]

        # Calculate the GeoTransform matrix for the output image, it has a different x and y origin
        output_geotransform = geotransform
        output_geotransform[0] = min_output_x
        output_geotransform[3] = max_output_y

        # Convert (x,y) pairs of output_geometry coordinates to pixel coordinates
        polygons_pixel = []
        for polygon in polygons:
            polygon_pixel = []
            for point in polygon:
                polygon_pixel.append(world_to_pixel(output_geotransform, point[0], point[1]))
            polygons_pixel.append(polygon_pixel)

        # Create a new PIL image and rasterize the clipping shape
        polygon_raster = Image.new("L", (output_cols, output_rows), 1)
        rasterize = ImageDraw.Draw(polygon_raster)

        for polygon in polygons_pixel:
            rasterize.polygon(polygon, 0)

        mask = image_to_array(polygon_raster)
        clip = gdalnumeric.choose(mask, (clip, 0)).astype(gdalnumeric.uint16)

        # Create the output file
        driver = gdal.GetDriverByName('GTiff')
        # !
        # proj = middle_image.GetProjection()
        output_image = driver.Create(output_image_path, output_cols, output_rows, 1, gdal.GDT_UInt16)
        output_image.GetRasterBand(1).WriteArray(clip)
        output_image.SetGeoTransform(output_geotransform)
        # !
        output_image.SetProjection(wkt_projection)
        output_image.FlushCache()
        output_image = None

    elif source_file_extension == '.jp2':
        source_image = gdal.Open(source_image_path)

        # TODO: output_image should be in UTM projection
        gdal.Warp(os.path.join(source_file_dir,
                               source_file_name
                               + '_WGS84'
                               + source_file_extension),
                  source_image,
                  dstSRS='EPSG:4326')

        source_image = gdal.Open(os.path.join(source_file_dir,
                                              source_file_name
                                              + '_WGS84'
                                              + source_file_extension))

        source_array = gdalnumeric.LoadFile(os.path.join(source_file_dir,
                                                         source_file_name
                                                         + '_WGS84'
                                                         + source_file_extension))
        geotransform = source_image.GetGeoTransform()

        min_source_x = geotransform[0]
        max_source_y = geotransform[3]

        source_cols = source_image.RasterXSize
        source_rows = source_image.RasterYSize

        pixel_size_source_x = geotransform[1]
        pixel_size_source_y = geotransform[5]
        max_source_x = min_source_x + (source_cols * pixel_size_source_x)
        min_source_y = max_source_y + (source_rows * pixel_size_source_y)

        image_wkt = 'POLYGON ((' \
                    + str(min_source_x) + ' ' \
                    + str(max_source_y) + ',' \
                    + str(max_source_x) + ' ' \
                    + str(max_source_y) + ',' \
                    + str(max_source_x) + ' ' \
                    + str(min_source_y) + ',' \
                    + str(min_source_x) + ' ' \
                    + str(min_source_y) + ',' \
                    + str(min_source_x) + ' ' \
                    + str(max_source_y) + '))'
        source_geometry = ogr.CreateGeometryFromWkt(image_wkt)

        shapefile = ogr.Open(SHP_PATH)
        shapefile_layer = shapefile.GetLayer("PL")
        shapefile_polygon = shapefile_layer.GetNextFeature()
        border_geometry = shapefile_polygon.GetGeometryRef()

        output_geometry = border_geometry.Intersection(source_geometry)
        output_geometry_type = output_geometry.GetGeometryType()
        output_geometry_geom_count = output_geometry.GetGeometryCount()

        # GetGeometryType() == 2: LINEARRING
        # GetGeometryType() == 3: POLYGON
        # GetGeometryType() == 6: MULTIPOLYGON
        polygons = []
        if output_geometry_type == 3:
            pts = output_geometry.GetGeometryRef(0)
            polygon = []
            for point in range(pts.GetPointCount()):
                polygon.append((pts.GetX(point), pts.GetY(point)))
            polygons.append(polygon)

        elif output_geometry_type == 6:
            for geom in range(output_geometry_geom_count):
                pts = output_geometry.GetGeometryRef(geom)
                pts = pts.GetGeometryRef(0)
                polygon = []
                for p in range(pts.GetPointCount()):
                    polygon.append((pts.GetX(p), pts.GetY(p)))
                polygons.append(polygon)

        min_output_x, max_output_x, min_output_y, max_output_y = get_geometry_extent(polygons)

        min_ouput_i, max_output_j = world_to_pixel(geotransform, min_output_x, max_output_y)
        max_output_i, min_output_j = world_to_pixel(geotransform, max_output_x, min_output_y)

        if min_ouput_i < 0:
            min_ouput_i = 0
        if max_output_j < 0:
            max_output_j = 0
        if max_output_i > source_cols:
            max_output_i = source_cols
        if min_output_j > source_rows:
            min_output_j = source_rows

        output_cols = int(max_output_i - min_ouput_i)
        output_rows = int(min_output_j - max_output_j)

        clip = source_array[max_output_j:min_output_j, min_ouput_i:max_output_i]

        output_geotransform = list(geotransform)
        output_geotransform[0] = min_output_x
        output_geotransform[3] = max_output_y

        polygons_pixel = []
        for polygon in polygons:
            polygon_pixel = []
            for point in polygon:
                polygon_pixel.append(world_to_pixel(output_geotransform, point[0], point[1]))
            polygons_pixel.append(polygon_pixel)

        polygon_raster = Image.new("L", (output_cols, output_rows), 1)
        rasterize = ImageDraw.Draw(polygon_raster)

        for polygon in polygons_pixel:
            rasterize.polygon(polygon, 0)

        mask = image_to_array(polygon_raster)

        clip = gdalnumeric.choose(mask, (clip, 0)).astype(gdalnumeric.uint16)

        driver = gdal.GetDriverByName('GTiff')
        output_image = driver.Create(output_image_path, output_cols, output_rows, 1, gdal.GDT_UInt16)
        output_image.GetRasterBand(1).WriteArray(clip)

        proj = source_image.GetProjection()
        output_image.SetGeoTransform(output_geotransform)
        output_image.SetProjection(proj)
        output_image.FlushCache()
        output_image = None

    else:
        print('unknown file format')


def zip_product(product_id, title):
    folder_path = os.path.join(TEMP_DIR, title)
    output_path = os.path.join(IMAGERY_DIR, product_id + '.zip')

    parent_folder = os.path.dirname(folder_path)

    contents = os.walk(folder_path)

    if os.path.exists(IMAGERY_DIR) == False:
        os.makedirs(IMAGERY_DIR)

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


def iterate_product(product_id, title, satellite):
    """
    Iterates over downloaded product content and calls the clip function for each imagery file (*.tiff or *.jp2).
    """

    if satellite[:2] == 'S1':
        if not os.path.exists(os.path.join(TEMP_DIR, title)):
            os.makedirs(os.path.join(TEMP_DIR, title))

        for image in os.listdir(os.path.join(TEMP_DIR, product_id, title + '.SAFE', 'measurement')):
            if image.endswith('.tiff'):
                source_image_path = os.path.join(TEMP_DIR, product_id, title + '.SAFE', 'measurement', image)
                output_image_path = os.path.join(TEMP_DIR, title, image)

                clip_image_to_shape(source_image_path, output_image_path)

        zip_product(product_id, title)

    elif satellite[:2] == 'S2':
        subfolder = os.listdir(os.path.join(TEMP_DIR, product_id, title + '.SAFE', 'GRANULE'))
        if title[4:10] == 'MSIL2A':
            for sub in subfolder:
                subsubfolder = os.listdir(os.path.join(TEMP_DIR, product_id, title + '.SAFE',
                                                       'GRANULE', sub, 'IMG_DATA'))
                for subsub in subsubfolder:
                    if not os.path.exists(os.path.join(TEMP_DIR, title, sub, subsub)):
                        os.makedirs(os.path.join(TEMP_DIR, title, sub, subsub))

                    for image in os.listdir(os.path.join(TEMP_DIR, product_id, title + '.SAFE',
                                                         'GRANULE', sub, 'IMG_DATA', subsub)):
                        if image.endswith('.jp2') and image[-11:-9] != 'SCL':
                            source_image_path = os.path.join(TEMP_DIR, product_id, title + '.SAFE',
                                                             'GRANULE', sub, 'IMG_DATA', subsub, image)
                            output_image_path = os.path.join(TEMP_DIR, title, sub, subsub, image)

                            clip_image_to_shape(source_image_path, output_image_path)

        else:
            for sub in subfolder:
                if not os.path.exists(os.path.join(TEMP_DIR, title, sub)):
                    os.makedirs(os.path.join(TEMP_DIR, title, sub))

                for image in os.listdir(os.path.join(TEMP_DIR, product_id, title + '.SAFE',
                                                     'GRANULE', sub, 'IMG_DATA')):
                    if image.endswith('.jp2'):
                        source_image_path = os.path.join(TEMP_DIR, product_id, title + '.SAFE',
                                                         'GRANULE', sub, 'IMG_DATA', image)
                        output_image_path = os.path.join(TEMP_DIR, title, sub, image)
                        clip_image_to_shape(source_image_path, output_image_path)

        zip_product(product_id, title)


@shared_task
def rolling_archive():
    boundary = AdministrativeUnit.objects.get(unit_name='POLSKA')
    boundary = boundary.poly[0]

    # time_range_end = timezone.now()
    # time_range_start = time_range_end - timedelta(days=14)

    time_range_end = timezone.now()
    time_range_start = time_range_end - timedelta(hours=6)

    expired_products = Product.objects.filter(is_downloaded=True,
                                              ingestion_date__lt=time_range_start)
    if expired_products:
        for product in expired_products:
            shutil.rmtree(os.path.join(BASE_DIR, product.id + '.zip'))
            product.is_downloaded = False
            product.save()

        print('deleted expired products')
    else:
        print('there are no expired products to delete')

    fresh_products = Product.objects.filter(is_downloaded=False,
                                            ingestion_date__gte=time_range_start,
                                            product_type='GRD',
                                            coordinates__coveredby=boundary)

    fresh_products_to_clip = Product.objects.filter(is_downloaded=False,
                                                    ingestion_date__gte=time_range_start,
                                                    product_type='GRD',
                                                    coordinates__overlaps=boundary)

    if fresh_products:
        for product in fresh_products:
            download_product(product.id)
            unzip_product(product.id)

            shutil.rmtree(os.path.join(TEMP_DIR, product.id + '.zip'))

            product.is_downloaded = True
            product.save()
        print('downloaded fresh products')
    else:
        print('there are no fresh products to download')

    if fresh_products_to_clip:
        for product in fresh_products_to_clip:
            download_product(product.id)
            unzip_product(product.id)

            shutil.rmtree(os.path.join(TEMP_DIR, product.id + '.zip'))
            iterate_product(product.id, product.title, product.satellite)

            product.is_downloaded = True
            product.save()
        print('downloaded and clipped fresh products')
    else:
        print('there are no fresh products to download and clip')
