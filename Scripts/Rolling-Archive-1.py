import numpy
from osgeo import gdal, gdalnumeric, ogr, osr
from PIL import Image, ImageDraw
import os, shutil, zipfile

### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

tempPath = 'D:\\test\\temp\\'
downloadedPath = 'D:\\test\\downloaded\\'
raster = "D:\\test\\shp_test\\L2A_T33UXR_20170928T100021_B03_10m_WGS84.jp2"
shp = "D:\\test\\temp\\PL"
output = "D:\\test\\shp_test\\clip"


# def downloadProduct(id, title):
#     url = "https://scihub.copernicus.eu/dhus/odata/v1/Products('" + id + "')/$value"  # URL zobrazowania na serwerze ESA
#
#     downloadPath = tempPath + title + '.zip'  # Sciezka pobranego obrazu                                                                        #Folder w ktorym rozpakowywany jest pobrany obraz
#
#     username = 'tprzybylek'
#     password = 'pracainz2015'
#
#     printMessage('Downloading product', startTime)
#     r = requests.get(url, auth=(username, password), stream=True)  # zadanie HTTP, pobranie pliku do pamieci
#     if r.status_code == 200:
#         with open(downloadPath, 'wb') as f:
#             r.raw.decode_content = True
#             shutil.copyfileobj(r.raw, f)  # zapis odebranego pliku w downloadPath
#             printMessage('Product downloaded', startTime)
#
#     sys.stdout.flush()


def unzipProduct(title):
    zip_ref = zipfile.ZipFile(tempPath + title + '.zip', 'r')
    zip_ref.extractall(tempPath)  # wypakowanie obrazu do extractPath
    zip_ref.close()


def zipProduct(id, title):
    folderPath = tempPath + id + '\\' + title + '\\'
    outputPath = downloadedPath + title + '.zip'

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

        print
        "'%s' created succesfully." % outputPath
    # except IOError, message:
    #     print
    #     message
    #     sys.exit(1)
    finally:
        zipFile.close()


def clipImage(raster, sourceImagePath, outputImagePath):
    def imageToArray(i):
        """
        Converts a Python Imaging Library array to a
        gdalnumeric image.
        """
        a = gdalnumeric.fromstring(i.tostring(), 'b')
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

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    srcImage = gdal.Open(sourceImagePath + raster + '.jp2')
    gdal.Warp(sourceImagePath + raster + '_WGS84.jp2', srcImage, dstSRS='EPSG:4326')

    ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ###

    srcImage = gdal.Open(sourceImagePath + raster + '_WGS84.jp2')
    srcArray = gdalnumeric.LoadFile(sourceImagePath + raster + '_WGS84.jp2')
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
    shapefile = ogr.Open("%s.shp" % shp)
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

    dst_filename = "%s.tif" % output
    # pxWidth = lrX - ulX
    # pxHeight = lrY - ulY
    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(outputImagePath + raster + '.tif', pxWidth, pxHeight, 1, gdal.GDT_UInt16)
    dataset.GetRasterBand(1).WriteArray(clip)

    proj = srcImage.GetProjection()
    dataset.SetGeoTransform(geoTrans)
    dataset.SetProjection(proj)
    dataset.FlushCache()
    dataset = None


def main(id, title):
    # downloadProduct(id, title)
    # unzipProduct(title)

    if not os.path.exists(tempPath + id):
        os.makedirs(tempPath + id)

    if (title[1] == '1'):
        # printMessage('Clipping image', startTime)
        # for image in os.listdir(extractPath + title + '.SAFE\\measurement\\'):
        #    if image.endswith('.tiff'):
        #        sourceImagePath = extractPath + title + '.SAFE\\measurement\\' + image
        #        outputImagePath = ordersPath + token + '\\' + title + '\\' + image
        #        clipImageTiff(extent, sourceImagePath, outputImagePath)
        pass

    elif (title[1] == '2'):
        subfolder = os.listdir(tempPath + title + '.SAFE\\GRANULE\\')

        if title[4:9] == 'MSIL2':
            for sub in subfolder:
                subsubfolder = os.listdir(tempPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\')

                for subsub in subsubfolder:
                    if not os.path.exists(tempPath + id + '\\' + title + '\\' + sub + '\\' + subsub):
                        os.makedirs(tempPath + id + '\\' + title + '\\' + sub + '\\' + subsub)
                        print
                        tempPath + id + '\\' + title + '\\' + sub + '\\' + subsub

                    for image in os.listdir(
                            tempPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\'):
                        if image.endswith('.jp2'):
                            sourceImagePath = tempPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + subsub + '\\'
                            outputImagePath = tempPath + id + '\\' + title + '\\' + sub + '\\' + subsub + '\\'
                            clipImage(image[:-4], sourceImagePath, outputImagePath)
        # else:
        #     for sub in subfolder:
        #         if not os.path.exists(ordersPath + token + '\\' + title + '\\' + sub):
        #             os.makedirs(ordersPath + token + '\\' + title + '\\' + sub)
        #
        #         for image in os.listdir(extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\'):
        #             if image.endswith('.jp2'):
        #                 sourceImagePath = extractPath + title + '.SAFE\\GRANULE\\' + sub + '\\IMG_DATA\\' + image
        #                 outputImagePath = ordersPath + token + '\\' + title + '\\' + sub + '\\' + image[:-4] + '.tiff'
        #                 clipImage(image[:-4], sourceImagePath, outputImagePath)

    zipProduct(id, title)

    # shutil.rmtree(tempPath + title + '.SAFE')
    # shutil.rmtree(tempPath + title + '.zip')


if __name__ == "__main__":
    # main(sys.argv[1], sys.argv[2])
    main('9376c3f7-54bc-45a3-b879-c0b26f9875ae', 'S2A_MSIL2A_20170928T100021_N0205_R122_T33UXR_20170928T100617')