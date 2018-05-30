from __future__ import absolute_import, unicode_literals
from celery import shared_task

import xml.etree.ElementTree
import requests
from datetime import datetime
from datetime import timedelta
import psycopg2
import time
import json


@shared_task
def update_database():
    def get_xml(url):
        passwords = json.load(open('/home/tomasz/PycharmProjects/copernicus-django/'
                                   'passwords.json'))

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
                    product['cloudcoverpercentage'] = attribute.text
                elif attribute.attrib['name'] == 'processingbaseline' and satellite[:2] == 'S2':
                    product['processingbaseline'] = attribute.text
                elif attribute.attrib['name'] == 'processinglevel' and satellite[:2] == 'S2':
                    product['processinglevel'] = attribute.text
        return product

    def build_query():
        sql_query = "INSERT INTO search_product (id, title, ingestion_date, satellite, " \
                    "mode, orbit_direction, cloud_cover, polarisation_mode, product_type, " \
                    "relative_orbit_number, size, coordinates, sensing_date, is_downloaded) " \
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        if 'cloudcoverpercentage' not in feature['properties']:
            feature['properties']['cloudcoverpercentage'] = None

        if 'polarisationmode' not in feature['properties']:
            feature['properties']['polarisationmode'] = None
            feature['properties']['mode'] = 'MSIL'

        if feature['properties']['mode'] == 'Earth Observation':
            feature['properties']['mode'] = 'EO'

        if len(feature['properties']['producttype']) > 8:
            feature['properties']['producttype'] = feature['properties']['producttype'][:8]

        sql_data = [
            feature['properties']['id'],
            feature['properties']['title'],
            feature['properties']['ingestiondate'],
            feature['properties']['satellite'],
            feature['properties']['mode'],
            feature['properties']['orbitdirection'],
            feature['properties']['cloudcoverpercentage'],
            feature['properties']['polarisationmode'],
            feature['properties']['producttype'],
            feature['properties']['relativeorbitnumber'],
            size_to_bytes(feature['properties']['size']),
            'SRID=4326;' + feature['geometry']['coordinates'],
            feature['properties']['sensingdate'],
            False
        ]

        return sql_query, sql_data

    last_update = get_last_update()

    last_product_time = last_update

    while last_update['lastUpdateTimeDifference'] > 3600 * 8:

        queryURI = 'https://scihub.copernicus.eu/apihub/search?q=ingestiondate:[' + last_update[
            'lastUpdateTime'].isoformat() + 'Z%20TO%20NOW]%20AND%20footprint:%22Intersects(' \
                                            'POLYGON((14.17%2054.14,18.19%2055.00,' \
                                            '23.69%2054.35,24.26%2050.50,' \
                                            '23.00%20 49.00,19.00%20 49.18,' \
                                            '14.68%2050.73,14.02%2052.84,' \
                                            '14.17%2054.14)))%22' \
                                            '&orderby=ingestiondate%20asc&rows=100'

        xmldoc = get_xml(queryURI)

        conn = psycopg2.connect(host="localhost", port="5432", database="copernicusexplorer",
                                user="django", password="CopExp2018")
        cur = conn.cursor()

        namespace = '{http://www.w3.org/2005/Atom}'

        for entry in xmldoc.iter(tag=namespace + 'entry'):
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Linestring',
                    'coordinates': ''
                }
            }

            product = get_product(entry)

            last_product_time = product['ingestiondate']

            # product['ingestiondate'] = product['ingestiondate'].__format__('%Y-%m-%d %H:%M:%S.%f')

            feature['properties'] = product

            print(product['id'])
            print(product['satellite'])
            print(product['producttype'])
            print(product['ingestiondate'].__format__('%Y-%m-%d %H:%M:%S.%f'))

            sql, data = build_query()
            cur.execute(sql, data)

        conn.commit()
        cur.close()
        conn.close()
        write_update_time('200', last_product_time)
        print('DB update successful')
        print('Waiting 15 secs')
        time.sleep(15)

        last_update = get_last_update()
    else:
        print("DB update complete")
