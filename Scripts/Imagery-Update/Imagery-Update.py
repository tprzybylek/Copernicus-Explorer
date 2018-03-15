import xml.etree.ElementTree
import requests
from datetime import datetime
from datetime import timedelta
import psycopg2
import time
import json


def get_xml(url):
    passwords = json.load(open('/home/tomasz/PycharmProjects/copernicus-django/'
                               'passwords.json'))

    r = requests.get(url, auth=(passwords['scihub']['user'], passwords['scihub']['password']))
    e = xml.etree.ElementTree.fromstring(r.content)
    return e


def open_xml(filename):
    e = xml.etree.ElementTree.parse(filename + '.xml').getroot()
    return e


def get_last_update():
    f = open('log.txt', 'r')
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


def write_update_time(status):
    f = open('log.txt', 'a')
    global last_product_time
    last_product_time = last_product_time + timedelta(milliseconds=1)
    f.write(last_product_time.__format__('%Y-%m-%d %H:%M:%S.%f')
            + ' ' + status + '\n')
    f.close()
    print("Writing last product time:",
          last_product_time.__format__('%Y-%m-%d %H:%M:%S.%f'))


def wkt_to_geojson(wkt):
    # UNUSED
    wkt = wkt.replace('POLYGON', 'LINESTRING')
    wkt = wkt.replace('((', ' ')
    wkt = wkt.replace('))', ' ')
    wkt = wkt.replace(',', ' ')

    words = wkt.split()[1:]
    n = [[float(words[x:x + 2][0]), float(words[x:x + 2][1])] for x in range(0, len(words), 2)]
    geojson = [n]
    return geojson


def size_to_bytes(size):
    if size[-2:] == 'GB':
        return str(int((float(size[:-3]) * (10 ** 9))))
    elif size[-2:] == 'MB':
        return str(int((float(size[:-3]) * (10 ** 6))))
    else:
        return None


def get_product(entry):
    for attribute in entry:
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


def build_query(satellite):
    if satellite[:2] == 'S1':
        sql_query = "INSERT INTO search_images1 (id, title, ingestiondate, satellite, " \
                   "mode, orbitdirection, polarisationmode, producttype, relativeorbitnumber, " \
                   "size, coordinates) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        sql_data = [
                    feature['properties']['id'],
                    feature['properties']['title'],
                    feature['properties']['ingestiondate'],
                    feature['properties']['satellite'],
                    feature['properties']['mode'],
                    feature['properties']['orbitdirection'],
                    feature['properties']['polarisationmode'],
                    feature['properties']['producttype'],
                    feature['properties']['relativeorbitnumber'],
                    size_to_bytes(feature['properties']['size']),
                    # feature['geometry']['coordinates']
                    'SRID=4326;' + feature['geometry']['coordinates']
                    # "ST_MakePolygon('" + feature['geometry']['coordinates'] + "')"
                   ]
    else:
        sql_query = "INSERT INTO search_images2 (id, title, ingestiondate, satellite, " \
                   "mode, cloudcover, orbitdirection, producttype, relativeorbitnumber, " \
                   "size, coordinates) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        if not feature['properties']['cloudcoverpercentage']:
            feature['properties']['cloudcoverpercentage'] = None

        sql_data = [
                    feature['properties']['id'],
                    feature['properties']['title'],
                    feature['properties']['ingestiondate'],
                    feature['properties']['satellite'],
                    feature['properties']['mode'],
                    feature['properties']['cloudcoverpercentage'],
                    feature['properties']['orbitdirection'],
                    feature['properties']['producttype'],
                    feature['properties']['relativeorbitnumber'],
                    size_to_bytes(feature['properties']['size']),
                    # feature['geometry']['coordinates']
                    'SRID=4326;' + feature['geometry']['coordinates']
                    # "ST_MakePolygon('" + feature['geometry']['coordinates'] + "')"
                   ]

    print(sql_data)
    return sql_query, sql_data


lastUpdate = get_last_update()

while lastUpdate['lastUpdateTimeDifference'] > 3600 * 6:

    queryURI = 'https://scihub.copernicus.eu/apihub/search?q=ingestiondate:[' + lastUpdate[
        'lastUpdateTime'].isoformat() + 'Z%20TO%20NOW]%20AND%20footprint:%22Intersects(' \
                                        'POLYGON((14.17%2054.14,18.19%2055.00,' \
                                        '23.69%2054.35,24.26%2050.50,' \
                                        '23.00%20 49.00,19.00%20 49.18,' \
                                        '14.68%2050.73,14.02%2052.84,' \
                                        '14.17%2054.14)))%22' \
                                        '&orderby=ingestiondate%20asc&rows=100'

    print('Query URI:', queryURI)

    xmldoc = get_xml(queryURI)

    # xmldoc = openXML('search')

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

        product['ingestiondate'] = product['ingestiondate'].__format__('%Y-%m-%d %H:%M:%S.%f')

        feature['properties'] = product

        print('satellite:', product['satellite'])
        print('id:', product['id'])
        print('ingestiondate:', product['ingestiondate'])
        print('--------------------------------')

        SQL, data = build_query(feature['properties']['satellite'])
        cur.execute(SQL, data)

    conn.commit()
    cur.close()
    conn.close()
    write_update_time('200')
    print('DB update successful')
    print('Waiting 15 secs')
    print("#### #### #### #### #### #### #### #### #### #### #### #### #### #### #### ####")
    time.sleep(15)

    lastUpdate = get_last_update()
else:
    print("DB update complete")
