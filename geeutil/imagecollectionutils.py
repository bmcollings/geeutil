# import modules
import ee
import geeutil.featureutils as featureutils
import geeutil.imageutils as imageutils
import geeutil.s2utils as s2_utils
import geeutil.lsutils as lsutils
import geeutil.ndutils as ndutils
import os
from tqdm.contrib.concurrent import thread_map
from itertools import repeat


# define valid sensors
valid_optical_sensors = {'S2', 'LS4', 'LS5', 'LS7', 'LS8', 'LS9', 'HLSL30', 'HLSS30'}
valid_sar_sensors = {'S1'}
# dict containing sensor optical image bands 
img_bands = {'S2': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7','B8', 'B8A', 'B11', 'B12'],
        'LS4': ['B1', 'B2', 'B3', 'B4', 'B5', 'B7'],
        'LS4_sr': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
        'LS5': ['B1', 'B2', 'B3', 'B4', 'B5', 'B7'],
        'LS5_sr': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
        'LS7': ['B1', 'B2', 'B3', 'B4', 'B5', 'B7'],
        'LS7_sr': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
        'LS8': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'HLSL30': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'Fmask'],
        'HLSS30': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7','B8', 'B8A', 'B11', 'B12', 'Fmask'],
        'LS8_sr': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        'LS9_sr': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        'S1': ['HH', 'HV', 'VV', 'VH', 'angle']}

# dict containing sensor GEE snippets for optical collections store SR and TOA collections as list
sensor_id = {'S2': ['COPERNICUS/S2_SR_HARMONIZED', 'COPERNICUS/S2_HARMONIZED'],
        'LS4': ['LANDSAT/LT04/C02/T1_L2', 'LANDSAT/LT04/C02/T1_TOA'],     
        'LS5': ['LANDSAT/LT05/C02/T1_L2', 'LANDSAT/LT05/C02/T1_TOA'],
        'LS7': ['LANDSAT/LE07/C02/T1_L2', 'LANDSAT/LE07/C02/T1_TOA'],
        'LS8': ['LANDSAT/LC08/C02/T1_L2', 'LANDSAT/LC08/C02/T1_TOA'],
        'LS9': ['LANDSAT/LC09/C02/T1_L2', 'LANDSAT/LC09/C02/T1_TOA'],
        'S1': ['COPERNICUS/S1_GRD'],
        'HLSL30': ['NASA/HLS/HLSL30/v002'],
        'HLSS30': ['NASA/HLS/HLSS30/v002']} 

# list of band names
band_names = ['blue', 'green', 'red', 'RE1', 'RE2', 'RE3', 'NIR', 'RE4', 'SWIR1', 'SWIR2']


def rename_img_bands(sensor):
    """function to rename optical image bands for ee.Image in ee.ImageCollection when using .map function
    
    Args
    sensor -  string sensor type that bands are being renamed
    
    returns 
    ee.Image with renamed bands
    """

    def rename(image):
        bands = img_bands[sensor]
        names = []
        if sensor == 'S2':
                names = band_names
        elif sensor == 'HLSS30':
               names = band_names[:6] + band_names[7:8] + band_names[6:7] + band_names[-2:] + ['Fmask']
        elif sensor == 'HLSL30':
               names = band_names[:3] + band_names[6:7] + band_names[-2:] + ['Fmask']
        else:
                names = band_names[:3] + band_names[6:7] + band_names[-2:]
        
        return image.select(bands).rename(names)
    
    return(rename)


def gen_imageCollection_from_shp(start_date, end_date, region_shp, sensor):
    """
    function that returns annual ee.ImageCollection for Landsat or Sentinel surface reflectance and top-of-atmosphere images.  
    
    Args
    start_date - string format yyyy-mm-dd
        end_date - string format yyyy-mm-dd
    sensor - sensor type to build composite image as string (S2, LS7, LS8)
    region_shp - shapefile defining region for composite, accepts polygons and lines, if polyline representing coastline output will be coast
            zone defined as 3km buffer zone around coastline
    
    returns
    ee.ImageCollection object for specified sensor, region and year
    """
    
    # raise error if sensor isn't compatible
    if sensor not in valid_optical_sensors:
            raise ValueError(sensor + ' is not compatible, must be S2, LS4, LS5, LS7 or LS8.')
    
    print("Generating composite image for {} from {} to {}".format(sensor, start_date, end_date))

    # convert region to ee.featureCollection 
    roi = featureutils.shp_to_featureCollection(region_shp)

    # define sr image collection
    collection = ee.ImageCollection(sensor_id[sensor][0]) \
        .filterBounds(roi) \
        .filterDate(start_date, end_date)
    
    return collection

def gen_imageCollection(start_date, end_date, roi, sensor, cloud_cover=None, surface_reflectance=True):
        """
        function that returns annual ee.ImageCollection for Landsat or Sentinel surface reflectance and top-of-atmosphere images.  

        Args
        start_date - string format yyyy-mm-dd
        end_date - string format yyyy-mm-dd
        sensor - sensor type to build composite image as string (S2, LS7, LS8)
        roi - ee.featureCollection object defining region of interest
        cloud_cover - integer representing cloud cover % for scenes to be included. Default=None and all scenes are considered. 

        returns
        ee.ImageCollection object for specified sensor, region and year
        """

        # raise error if sensor isn't compatible
        if sensor not in valid_optical_sensors:
                raise ValueError(sensor + ' is not compatible, must be S2, LS4, LS5, LS7 or LS8.')

        # define sr image collection
        collection = ee.ImageCollection(sensor_id[sensor][0]) \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        
        # perform sentinel cloudmasking 
        if sensor == 'S2':
                # filter collection by cloud cover if cloud_cover is not none
                if cloud_cover is not None: 
                        collection = collection.filterMetadata('CLOUDY_PIXEL_PERCENTAGE', 'less_than', cloud_cover)
                
                # join sentinel cloud probabilty
                img_collection = s2_utils.join_S2_cld_prob(collection, roi, start_date, end_date)

                # map cloud masking workflow over collection
                img_collection = (img_collection 
                        # add is_clouds band
                        .map(s2_utils.add_cloud_shadow_mask) 
                        # add cloud_shdw_mask # use default buffer value (50m)
                        # mask clouds
                        .map(s2_utils.mask_clouds)
                        # rename bands
                        .map(rename_img_bands(sensor)))
                
        elif sensor == 'HLSL30' or sensor == 'HLSS30':
               # filter collection by cloud cover if cloud_cover is not none
                if cloud_cover is not None: 
                        collection = collection.filterMetadata('CLOUD_COVERAGE', 'less_than', cloud_cover)
                
                # run landsat cloudmasking and rename bands
                img_collection = (collection 
                        .map(lsutils.mask_clouds_HLS) 
                        .map(rename_img_bands(sensor)))
                
        # perform landsat cloudmasking
        else:
                # add SR if surface_reflectance=True for band names
                if surface_reflectance == True:
                       sensor = f'{sensor}_sr'
                else:
                       sensor = sensor
                # filter collection by cloud cover if cloud_cover is not none
                if cloud_cover is not None: 
                        collection = collection.filterMetadata('CLOUD_COVER', 'less_than', cloud_cover)
                
                # run landsat cloudmasking and rename bands
                img_collection = (collection 
                        .map(lsutils.mask_clouds_LS_qa) 
                        .map(rename_img_bands(sensor)))

        return img_collection

def return_least_cloudy_image(start_date, end_date, roi, sensor, cloud_cover=None, return_least_cloudy=True):
        """
        function that returns annual ee.ImageCollection for Landsat or Sentinel surface reflectance and top-of-atmosphere images.  

        Args
        start_date - string format yyyy-mm-dd
        end_date - string format yyyy-mm-dd
        sensor - sensor type to build composite image as string (S2, LS7, LS8)
        roi - ee.featureCollection object defining region of interest
        cloud_cover - integer representing cloud cover % for scenes to be included. Default=None and all scenes are considered. 

        returns
        ee.ImageCollection object for specified sensor, region and year
        """

        # raise error if sensor isn't compatible
        if sensor not in valid_optical_sensors:
                raise ValueError(sensor + ' is not compatible, must be S2, LS5, LS7 or LS8.')

        # define sr image collection
        collection = ee.ImageCollection(sensor_id[sensor][1]) \
        .filterBounds(roi) \
        .filterDate(start_date, end_date) \
        
        if sensor == 'S2':
                if cloud_cover is not None: 
                        collection = collection.filterMetadata('CLOUDY_PIXEL_PERCENTAGE', 'less_than', cloud_cover) \
                        .sort('CLOUDY_PIXEL_PERCENTAGE', return_least_cloudy) \
                        .map(rename_img_bands(sensor))
        else:
                if cloud_cover is not None: 
                        collection = collection.filterMetadata('CLOUD_COVER', 'less_than', cloud_cover) \
                        .sort('CLOUD_COVER', return_least_cloudy) \
                        .map(rename_img_bands(sensor))

        return ee.Image(collection.first())

def download_images_in_collection(ee_collection, region_of_interest, image_bands,  image_directory_path,
                                  crs="EPSG:2193", pixel_size=20, no_data_val=-99):
        """
        function to download imagery in ee.ImageCollection object to a local directory as GeoTiff files. 

        Args
        img_collection - ee.ImageCollection object with imagery to download
        region_of_interest - ee.FeatureCollection object of area for which image will be downloaded
        image_bands - list of image bands that are to be downloaded
        image_directory_path - path to directory where imagery will be saved
        crs - coordinate reference system for downloaded images
        pixel_size - integer representing spatial resolution of downloaded images
        no_data_val - integer representing no data val for unvalid data in images
        """
        # calculate ndvi and mndwi
        ee_collection = (ee_collection.map(ndutils.apply_ndvi)
                        .map(ndutils.apply_mndwi))
        
        # return collection as list 
        img_list = ee_collection.toList(ee_collection.size().getInfo())

        def down_img_mt(img_id, img_collection_list, directory, roi, crs, scale, no_data_val):
            img = ee.Image(img_collection_list.get(img_id)).select(image_bands)
            img = img.clip(roi).unmask(no_data_val) # clip img for export
            system_index = img.get("system:index").getInfo() # fn of image = system_index
            fn = f"{system_index}.tif"
            image_path = f"{directory}/{fn}"
            if os.path.exists(f"{image_path}"):
                print(f"{fn} already downloaded.")
            else:
                try:
                    imageutils.download_img_local(img.toFloat(), directory, fn, roi.geometry(), crs, scale)
                except:
                    print(f"issue with {fn}, continuing")
        
        iterator = list(range(0, ee_collection.size().getInfo()))
        
        try:
                thread_map(down_img_mt, iterator, repeat(img_list), repeat(image_directory_path), repeat(region_of_interest), repeat(crs), repeat(pixel_size), repeat(no_data_val))
                print("images downloaded.")
        except ee.ee_exception.EEException as e:
               print(f"Encountered earthenging error: {e}. Error raised...")
        raise               