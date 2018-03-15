import os
import tempfile
import zipfile

import errno
import requests
import xml.etree.cElementTree as ElementTree
from datetime import datetime, timedelta
from osgeo import gdal

import shutil
import json


passwords = json.load(open('/home/tomasz/PycharmProjects/copernicus-django/passwords.json'))

ESA_USERNAME = passwords['scihub']['user']
ESA_PASSWORD = passwords['scihub']['password']
ESA_URI = 'https://scihub.copernicus.eu/apihub/'
ESA_FILE_URI = "https://scihub.copernicus.eu/dhus/odata/v1/" \
               "Products('{id}')/$value"
ESA_BOUNDARIES_WKT = 'POLYGON((14.17 54.14, 18.19 55.00, 23.69 54.35, 24.26 50.50, ' \
                     '23.00 49.00, 19.00 49.18, 14.68 50.73, 14.02 52.84, 14.17 54.14))'
ESA_DOWNLOAD_PATH = '/home/rimmon/webdysk/ESA/ESA2/'



class MetadataDownloader:
    def __init__(self, starttime=datetime.now(),
                 endtime=None):
        self.username = ESA_USERNAME
        self.password = ESA_PASSWORD
        self.api_uri = ESA_URI
        self.search_uri = os.path.join(self.api_uri, 'search')
        self.boundaries_wkt = ESA_BOUNDARIES_WKT

        self.starttime = starttime
        self.endtime = endtime

    def _build_payload(self, page, rows):
        params = dict()
        start = (page-1)*rows
        params['q'] = \
            'ingestiondate:[{starttime} TO {endtime}] ' \
            'AND footprint:"Intersects({boundaries})"'.format(
                starttime=self.starttime.isoformat() + 'Z',
                endtime=self.endtime.isoformat() + 'Z' if self.endtime else
                'NOW',
                boundaries=self.boundaries_wkt,
            )
        params['orderby'] = 'ingestiondate asc'
        params['rows'] = str(rows)
        params['start'] = str(start)
        return params

    def get_xml(self, page=1, rows=100):
        r = requests.get(
            self.search_uri,
            auth=(self.username, self.password),
            params=self._build_payload(page, rows))
        return r.content

    def get_products(self, xml=None, page=1, rows=100):
        if not xml:
            xml = self.get_xml(page, rows)
        tree = ElementTree.fromstring(xml)
        namespace = '{http://www.w3.org/2005/Atom}'
        entries = list()
        for entry in tree.iter(tag=namespace + 'entry'):
            e = dict()
            for attr in entry:
                key = attr.get('name', attr.tag.replace(namespace, ''))
                if key in ['id', 'producttype']:
                    e[key] = attr.text
            entries.append(e)
        return entries

    def get_data(self):
        products = list()
        page = 1
        per_page = 100
        output = []
        while products or page == 1:
            products = self.get_products(page=page, rows=per_page)
            page += 1
            output += products
        return output


def cutToKml(input, output, kml):
    gdal.Warp(output, input, format='GTiff',
                  cutlineDSName=kml, dstNodata=0)


def get_file(product_id):

    uri = ESA_FILE_URI.format(id=product_id)
    r = requests.get(uri, auth=(ESA_USERNAME,
                                ESA_PASSWORD), stream=True)
    if r.status_code == 200:
        path = os.path.join(ESA_DOWNLOAD_PATH, '{}.zip'.format(product_id))
        with open(path, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)


def process_images(product_id, kml):
    path = os.path.join(ESA_DOWNLOAD_PATH, '{}.zip'.format(
        product_id))
    extractpath = os.path.join(ESA_DOWNLOAD_PATH)

    with open(path, "rb") as zipsrc:
        zfile = zipfile.ZipFile(zipsrc)
        filename = zfile.filelist[0].filename
        for member in zfile.infolist():
            target_path = os.path.join(extractpath, member.filename)
            if target_path.endswith('/'):  # folder entry, create
                try:
                    os.makedirs(target_path)
                except (OSError, IOError) as err:
                    # Windows may complain if the folders already exist
                    if err.errno != errno.EEXIST:
                        raise
                continue
            with open(target_path, 'wb') as outfile, zfile.open(member) as infile:
                shutil.copyfileobj(infile, outfile)

    directory_path = os.path.join(extractpath, filename[:-1],
                                  'measurement')
    for i, image in enumerate(os.listdir(directory_path)):
        if image.endswith('.tiff'):
            imagepath = os.path.join(directory_path, image)

            gdal.Warp('.'.join(imagepath.split('.')[:-1]) +
                          '-processed.tiff', imagepath, format='GTiff',
                      cutlineDSName=kml, dstNodata=0)


if __name__ == '__main__':
    date = datetime.now() - timedelta(days=1)
    downloader = MetadataDownloader(starttime=date)
    grd_ids = [x['id'] for x in downloader.get_data() if x['producttype'] == 'GRD']
    path = os.path.join(tempfile._get_default_tempdir(), next(
        tempfile._get_candidate_names()) + '.kml')
    tmp = open(path, 'w')
    for product_id in grd_ids:
        get_file(product_id)
    kml_content = """<?xml version = "1.0" encoding = "UTF-8"?>
            <kml xmlns = "http://www.opengis.net/kml/2.2">
                <Placemark>
                <Polygon><outerBoundaryIs><LinearRing><coordinates>14.17,54.14,0 18.19,55.0,0 23.69,54.35,0 24.26,50.5,0 23.0,49.0,0 19.0,49.18,0 14.68,50.73,0 14.02,52.84,0 14.17,54.14,0</coordinates></LinearRing></outerBoundaryIs></Polygon> 
                </Placemark>
            </kml>"""
    tmp.write(kml_content)
    tmp.close()
    for product_id in grd_ids:
        process_images(product_id, tmp.name)
    os.remove(tmp.name)



