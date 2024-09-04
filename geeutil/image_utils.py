# import modules
import ee
import time
import os
import requests
from osgeo import gdal


# Initialize GEE
ee.Initialize()


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
            raise exception("Could not open the image band: ", band)


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