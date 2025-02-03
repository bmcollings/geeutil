# import modules
import ee
import time
import os
import requests
from osgeo import gdal


def rename_img_bands(img_bands, band_names):
    """function to rename optical image bands for ee.Image in ee.ImageCollection when using .map function
    
    Args
    img_bands - list, list of band values to be renamed
    band_names - list, list of band names
    
    returns 
    ee.Image with renamed bands
    """

    def rename(image):
        bands = img_bands
        return image.select(bands).rename(band_names)
    
    return(rename)

def resample_image(image, crs='EPSG: 2193', pixel_size=20):
    """
    function to resample ee.image object 
    
    Args
    image - ee.image object to be resampled
    crs - reference system as epsg code
    pixel_size - resampled pixel size"""

    bands = image.bandNames()
    resampled_bands = image.select(bands).reproject({'crs': crs, 'scale': pixel_size})
    return resampled_bands

def run_task(task, mins):
    """
    function to run ee.batch.export and check status of task every number of minutes specified by mins
    """

    secs = mins * 60
    task.start()
    while task.active():
        print(task.status())
        time.sleep(secs)

def set_band_names(image, band_names):
    """
    Function to set band names
    :param image: input image
    :param band_names: list of band names
    """
    data = gdal.Open(image, gdal.GA_Update)
    for i in range(len(band_names)):
        band = i + 1
        bandName = band_names[i]

        imgBand = data.GetRasterBand(band)
        # Check the image band is available
        if not imgBand is None:
            imgBand.SetDescription(bandName)
        else:
            raise Exception("Could not open the image band: ", band)


def download_img_local(ee_image, folder, name, region, crs, scale, format='GEO_TIFF'):
    """
    function to get download url from ee.Image
    
    Args
    ee_image - ee.Image object
    folder - local folder name to save image to
    name - file_name
    region - extent of image
    scale - output_resolution
    format - image format default GEO_TIFF

    Returns
    image downloaded to local folder specified
    """
    
    # get bandnames

    bands = ee_image.bandNames().getInfo()
    #print(bands)
    params = {
        'bands': bands,
        'region': region,
        'crs': crs,
        'scale': scale,
        'format': format
    }
    # join folder and file name
    down_path = os.path.join(folder, name)

    # define url
    try: 
        url = ee_image.getDownloadUrl(params)
    except Exception as e:
        print('Error occurred during download.')
        print(e)
        return

    # get url 
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print('Error occurred during download.')
        print(response.json()["error"]["message"])
        return

    # download file 
    with open(down_path, 'wb') as fd:
        for chunk in response.iter_content(chunk_size=1024):
            fd.write(chunk)

    # set band names
    set_band_names(down_path, bands)

def set_nodata_val(image, no_data_val):
    """
    function to set no data value for image
    
    Arg
    image - str, filepath to image requiring no_data value
    no_data_val - int, no data value to set
    """
    ds = gdal.OpenEx(image, gdal.GA_Update)
    for i in range(ds.RasterCount):
        ds.GetRasterBand(i + 1).SetNoDataValue(no_data_val)

def clip_images_to_region(region):
    """
    function to clip images in ee.ImageCollection using .map() to region defined by featureCollection
    Args
    region - ee.featureCollection representing the region to be clipped to. 
    """
    def clip(img):
        return img.clipToCollection(region)
    return(clip)

def return_region_pxl_count(img):
    """
    function to return number of pixels in image, based on one band in image defined by band_name. 
    """
    # def calc_pxl_count(img):
    band = img.bandNames().get(0) # define first band name from image
    pxl_count = img.select([band]).reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=img.geometry(),
        maxPixels=1e10
    )
    return img.set('region_pixel_count', ee.Number(pxl_count.get(band)))

def return_cloud_pxl_count(img):
    """"
    function to return number of cloudy pixels in an image. Image must contain cloud mask band where band name = 'cloud'
    """
    cloud_mask = img.select('clouds') # cloud band is called clouds
    band =  img.bandNames().get(0) # define first band name from image
    # updateMask to ensure only count of cloudy pixels are returned
    mask_img = img.select([band]).updateMask(cloud_mask)
    pxl_count = mask_img.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=img.geometry(),
        maxPixels=1e10
    )
    return img.set('mask_pixel_count', ee.Number(pxl_count.get(band)))

def add_cell_level_cloud_cover_property(img):
    """
    function to return cell level cloud cover as image metadata property.
    """
    return img.set('region_cloudy_percent', ee.Number(img.get('mask_pixel_count')).divide(ee.Number(img.get('region_pixel_count'))))