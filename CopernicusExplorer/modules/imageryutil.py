import sys
import os
import requests
import zipfile
import shutil
import json
import numpy
from osgeo import ogr, osr, gdal

DOWNLOAD_PATH = '/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/CopernicusExplorer/static/imagery/'
ORDERS_PATH = '/home/tomasz/PycharmProjects/copernicus-django/CopernicusExplorer/CopernicusExplorer/static/orders/'


def download_product(id):
    """
    Downloads a Sentinel product from ESA archive and writes it to the hard drive
    :param str id: Product ID
    """

    url = "https://scihub.copernicus.eu/dhus/odata/v1/Products('" + id + "')/$value"

    # TODO: load password from file
    username = 'tprzybylek'
    password = 'pracainz2015'

    r = requests.get(url, auth=(username, password), stream=True)
    if r.status_code == 200:
        with open(DOWNLOAD_PATH + id + '.zip', 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

    sys.stdout.flush()


def is_downloaded(id):
    """
    Checks if a product is already downloaded
    :param str id: Product ID
    :return bool:
    """

    if os.path.isfile(DOWNLOAD_PATH + id + '.zip'):
        return True
    else:
        return False


def unzip_product(id):
    """
    Unzips the product to /DOWNLOAD_PATH/id/
    :param str id: Product ID
    """

    zip_ref = zipfile.ZipFile(DOWNLOAD_PATH + id + '.zip', 'r')
    zip_ref.extractall(DOWNLOAD_PATH + id)  # wypakowanie obrazu do extractPath
    zip_ref.close()


def zip_order(order_id):
    """
    Zips a requested order to the /ORDERS_PATH/order_id.zip file
    :param str order_id: Order ID
    """

    folder_path = ORDERS_PATH + order_id + '/'
    output_path = ORDERS_PATH + order_id + '.zip'

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

        print(output_path + ' created succesfully.')
    except IOError:
        sys.exit(1)
    finally:
        zipFile.close()


def clipImageTiff(extent, source_image_path, output_image_path):
    """
    Clips a GeoTIFF image to defined geographical extent and saves it to a .tiff file

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

    i1 = int((extent['minX'] - xOrigin) / pixelWidth)
    j1 = int((extent['minY'] - yOrigin) / pixelHeight)
    i2 = int((extent['maxX'] - xOrigin) / pixelWidth)
    j2 = int((extent['maxY'] - yOrigin) / pixelHeight)

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


def clipImageJP2(extent, source_image_path, output_image_path):
    """
    Clips a JPEG2000 image to defined geographical extent and saves it to a .jp2 file

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

    i1j1 = transform.TransformPoint(extent['minX'], extent['minY'])
    i2j2 = transform.TransformPoint(extent['maxX'], extent['maxY'])

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


def clip_image(token, extent, title, satellite):
    if not os.path.exists(ORDERS_PATH + token + '\\' + title):
        os.makedirs(ORDERS_PATH + token + '\\' + title)

    if (satellite[:2] == 'S1'):
        # printMessage('Clipping image', startTime)
        for image in os.listdir(DOWNLOAD_PATH + title + '.SAFE\\measurement\\'):
            if image.endswith('.tiff'):
                sourceImagePath = DOWNLOAD_PATH + title + '.SAFE\\measurement\\' + image
                outputImagePath = ORDERS_PATH + token + '\\' + title + '\\' + image
                clipImageTiff(extent, sourceImagePath, outputImagePath)

    elif (satellite[:2] == 'S2'):
        # printMessage('Clipping image', startTime)

        subfolder = os.listdir(DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\')
        print(title[4:10])
        if title[4:10] == 'MSIL2A':
            for sub in subfolder:

                subsubfolder = os.listdir(DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\')
                print(subsubfolder)

                for subsub in subsubfolder:
                    if not os.path.exists(ORDERS_PATH + token + '\\' + title + '\\' + sub + '\\' + subsub):
                        os.makedirs(ORDERS_PATH + token + '\\' + title + '\\' + sub + '\\' + subsub)
                        print(ORDERS_PATH + token + '\\' + title + '\\' + sub + '\\' + subsub)

                    for image in os.listdir(
                            DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\'):
                        if image.endswith('.jp2'):
                            sourceImagePath = DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\' + image
                            outputImagePath = ORDERS_PATH + token + '\\' + title + '\\' + sub + '\\' + subsub + '\\' + image[
                                                                                                                      :-4] + '.tiff'
                            clipImageJP2(extent, sourceImagePath, outputImagePath)
        else:
            for sub in subfolder:
                if not os.path.exists(ORDERS_PATH + token + '\\' + title + '\\' + sub):
                    os.makedirs(ORDERS_PATH + token + '\\' + title + '\\' + sub)
                for image in os.listdir(DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\'):
                    if image.endswith('.jp2'):
                        sourceImagePath = DOWNLOAD_PATH + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + image
                        outputImagePath = ORDERS_PATH + token + '\\' + title + '\\' + sub + '\\' + image[:-4] + '.tiff'
                        clipImageJP2(extent, sourceImagePath, outputImagePath)