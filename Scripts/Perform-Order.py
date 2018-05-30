import os
import sys
import gdal
import requests
import zipfile, shutil
import json
import time
import numpy
from osgeo import ogr, osr


startTime = time.time()

# order = '{"token":"p1uc5bcn","orderedTime":1508412083239,"completedTime":1508412083,"extent":{"minX":16.592376683838665,"maxX":16.76403806079179,"minY":50.39132745387828,"maxY":50.51199652418108},"cart":[{"ID":"9376c3f7-54bc-45a3-b879-c0b26f9875ae","title":"S2A_MSIL2A_20170928T100021_N0205_R122_T33UXR_20170928T100617","satellite":"S2A"}],"email":"example@example.com","status":"0"}'

# order = '{"token":"6b8jld9y","orderedTime":1507033205159,"completedTime":1507033205,"extent":{"minX":13.893173192627728,"maxX":14.189804052002726,"minY":50.897717175804516,"maxY":50.996352918763},"cart":[{"ID":"ca49f1ba-cd24-43d3-b6ae-5ed5ae5f7b8b","title":"S2A_OPER_PRD_MSIL1C_PDMC_20160828T210754_R022_V20160827T101022_20160827T101025","satellite":"S2A"}],"email":"example@example.com","status":"0"}'
# order = '{"token":"6ewqnu0r","orderedTime":1506515962901,"completedTime":1506515963,"extent":{"minX":13.893173192627728,"maxX":14.189804052002726,"minY":50.897717175804516,"maxY":50.996352918763},"cart":[{"ID":"8b61bae7-d96d-4d7d-9d83-a653e2913ea4","title":"S1B_IW_GRDH_1SDV_20170102T165051_20170102T165116_003672_0064CF_5582","satellite":"S1B"}],"email":"example@example.com","status":"0"}'

extractPath = 'D:\\test\\downloaded\\'
ordersPath = 'D:\\test\\orders\\'


############################


def printMessage(message, startTime):
    print(message + ' ' + str(time.time() - startTime))


def isDownloaded(title):
    if os.path.isfile(extractPath + title + '.zip'):
        return True
    else:
        return False


def downloadProduct(order, cartElement):
    url = "https://scihub.copernicus.eu/dhus/odata/v1/Products('" + cartElement['ID'] + "')/$value"  # URL zobrazowania na serwerze ESA

    downloadPath = extractPath + cartElement['title'] + '.zip'
    # Sciezka pobranego obrazu
    # Folder w ktorym rozpakowywany jest pobrany obraz

    username = 'tprzybylek'
    password = 'pracainz2015'

    printMessage('Downloading product', startTime)
    r = requests.get(url, auth=(username, password), stream=True)  # zadanie HTTP, pobranie pliku do pamieci
    if r.status_code == 200:
        with open(downloadPath, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)  # zapis odebranego pliku w downloadPath
            printMessage('Product downloaded', startTime)

    sys.stdout.flush()


def unzipProduct(title):
    printMessage('Extracting product', startTime)
    zip_ref = zipfile.ZipFile(extractPath + title + '.zip', 'r')
    zip_ref.extractall(extractPath)  # wypakowanie obrazu do extractPath
    zip_ref.close()
    printMessage('Product extracted', startTime)


def zipOrder(token):
    folderPath = ordersPath + token + '\\'
    outputPath = ordersPath + token + '.zip'

    parentFolder = os.path.dirname(folderPath)

    contents = os.walk(folderPath)

    try:
        zipFile = zipfile.ZipFile(outputPath, 'w', zipfile.ZIP_DEFLATED)
        for root, folders, files in contents:
            for folderName in folders:
                absolutePath = os.path.join(root, folderName)
                relativePath = absolutePath.replace(parentFolder + '\\', '')
                zipFile.write(absolutePath, relativePath)

            for fileName in files:
                absolutePath = os.path.join(root, fileName)
                relativePath = absolutePath.replace(parentFolder + '\\', '')
                zipFile.write(absolutePath, relativePath)

        print("'%s' created succesfully." % outputPath)
    except IOError:
        sys.exit(1)
    finally:
        zipFile.close()


def clipImages(token, extent, title, satellite):
    def clipImageTiff(extent, sourceImagePath, outputImagePath):
        WKT_Projection = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

        dataset = gdal.Open(sourceImagePath)
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

        dst_ds = gdal.GetDriverByName('GTiff').Create(outputImagePath, new_cols, new_rows, bands=1, eType=gdal.GDT_Byte)

        dst_ds.SetProjection(WKT_Projection)
        dst_ds.SetGCPs(newGCPs, WKT_Projection)

        dst_ds.GetRasterBand(1).WriteArray(data)

        dst_ds = None
        dataset_middle = None

    def clipImageJP2(extent, sourceImagePath, outputImagePath):
        WGS84_projection = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

        in_srs = osr.SpatialReference()
        in_srs.ImportFromWkt(WGS84_projection)

        dataset = gdal.Open(sourceImagePath)
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

            dst_ds = gdal.GetDriverByName('GTiff').Create(outputImagePath, new_cols, new_rows, bands=1,
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

    if not os.path.exists(ordersPath + token + '\\' + title):
        os.makedirs(ordersPath + token + '\\' + title)

    if (satellite[:2] == 'S1'):
        printMessage('Clipping image', startTime)
        for image in os.listdir(extractPath + title + '.SAFE\\measurement\\'):
            if image.endswith('.tiff'):
                sourceImagePath = extractPath + title + '.SAFE\\measurement\\' + image
                outputImagePath = ordersPath + token + '\\' + title + '\\' + image
                clipImageTiff(extent, sourceImagePath, outputImagePath)

    elif (satellite[:2] == 'S2'):
        printMessage('Sattelite not supported...yet', startTime)
        printMessage('Clipping image', startTime)

        subfolder = os.listdir(extractPath + title + '.SAFE\\GRANULE\\')
        print(title[4:10])
        if title[4:10] == 'MSIL2A':
            for sub in subfolder:

                subsubfolder = os.listdir(extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\')
                print(subsubfolder)

                for subsub in subsubfolder:
                    if not os.path.exists(ordersPath + token + '\\' + title + '\\' + sub + '\\' + subsub):
                        os.makedirs(ordersPath + token + '\\' + title + '\\' + sub + '\\' + subsub)
                        print(ordersPath + token + '\\' + title + '\\' + sub + '\\' + subsub)

                    for image in os.listdir(
                            extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\'):
                        if image.endswith('.jp2'):
                            sourceImagePath = extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\' + image
                            outputImagePath = ordersPath + token + '\\' + title + '\\' + sub + '\\' + subsub + '\\' + image[
                                                                                                                      :-4] + '.tiff'
                            clipImageJP2(extent, sourceImagePath, outputImagePath)
        else:
            for sub in subfolder:
                if not os.path.exists(ordersPath + token + '\\' + title + '\\' + sub):
                    os.makedirs(ordersPath + token + '\\' + title + '\\' + sub)
                for image in os.listdir(extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\'):
                    if image.endswith('.jp2'):
                        sourceImagePath = extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + image
                        outputImagePath = ordersPath + token + '\\' + title + '\\' + sub + '\\' + image[:-4] + '.tiff'
                        clipImageJP2(extent, sourceImagePath, outputImagePath)

    else:
        printMessage('Sattelite not supported', startTime)


############################

def main(order):
    j = json.loads(order)

    for product in j['cart']:
        print(product['title'])

        if isDownloaded(product['title']):
            printMessage('Is downloaded', startTime)
        else:
            printMessage('Is not downloaded', startTime)
            downloadProduct(j, product)

        unzipProduct(product['title'])

        clipImages(j['token'], j['extent'], product['title'], product['satellite'])

    zipOrder(j['token'])

    j['status'] = '1'
    j['completedTime'] = time.time()

    ordersFilePath = 'C:\\Users\\20274\\OneDrive\\Dokumenty\\Visual Studio 2017\\Projects\\Imagery-Explorer\\Imagery-Explorer\\public\\orders.json'

    with open(ordersFilePath, 'r+') as f:
        fJ = json.load(f)
        for n, i in enumerate(fJ):
            if i['token'] == j['token']:
                fJ[n] = j
        f.close()

    with open(ordersFilePath, 'w') as f:
        json.dump(fJ, f)
        f.close()

    # printMessage('Deleting temporary files', startTime)

    # for product in j['cart']:
    #     shutil.rmtree(extractPath + product['title'] + '.SAFE')

    # shutil.rmtree(ordersPath + j['token'])

    print('------------------------------------------')
    printMessage('Total time in seconds', startTime)
    print('------------------------------------------')


if __name__ == "__main__":
    main(sys.argv[1])
    # main(order)
