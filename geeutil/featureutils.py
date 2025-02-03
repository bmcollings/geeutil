# import modules 
import ee
import geopandas as gpd
import json



def shp_to_featureCollection(shapefile):
    """
    function to read a shapefile as a ee.featureCollection using geopandas
    
    Args
    shapefile - path to shapefile to be read as featureCollection GEE object
    
    Returns
    ee.FeatureCollection object"""
    # read shapefile as gdf
    gdf = gpd.read_file(shapefile)
    # convert gdf to featureCollection with gdf_to_featureCollection
    return gdf_to_featureCollection(gdf)

    
def buffer(buffer):
    """
    function to buffer features in featureCollection
    Args 
    featureCollection - ee.object to be buffered 
    buffer - buffer distance in metres

    returns
    buffered ee.featureCollection
    """
    def apply_buffer(feature):
        return feature.buffer(buffer)
    
    return apply_buffer


def gdf_to_featureCollection(gdf):
    '''
    function to read a geopandas dataframe as a ee.featureCollection
    Args
    gdf - geopandas dataframe to be read as featureCollection GEE object
    
    Returns
    ee.FeatureCollection object
    '''
    # raise error if gdf is not LineString or Polygon
    valid_geometry = {'LineString','Polygon'}
    if gdf.geom_type[0] not in valid_geometry:
        raise ValueError('Shapefile must be LineString or Polygon.')

    #convert to json_dict
    if gdf.geom_type[0] == 'LineString':
        #gdf = gdf.buffer(1500)
        gdf = gdf.to_crs(4326)
    else:
        gdf = gdf.to_crs(4326)
    geo_json = gdf.to_json()
    json_dict = json.loads(geo_json)
    features = []
    # iterate over json features convert ee.Geometries and read as ee.Feature
    for feature in json_dict['features']:
        # derive ee.Geometry type from json_dict
        if feature['geometry']['type'] == 'LineString':
            line = ee.Feature(ee.Geometry.LineString(feature['geometry']['coordinates']))
            features.append(line.buffer(1500))
        if feature['geometry']['type'] == 'Polygon':
            features.append(ee.Feature(ee.Geometry.Polygon(feature['geometry']['coordinates'])))
    
    return ee.FeatureCollection(features)

def item_to_featureCollection(dict_item):
    """
    function to return ee.FeatureCollection from dict_item generated from pandas iterfeatures
    
    args
    dict_item - geodataframe item to be read as featureCollection

    returns 
    ee.FeatureCollection object
    """

    # raise error if gdf is not LineString or Polygon
    valid_geometry = {'LineString','Polygon','Point', 'MultiPolygon'}
    if dict_item['geometry']['type'] not in valid_geometry:
        raise ValueError('Shapefile must be a valid geometry.')

    features = []

    if dict_item['geometry']['type'] == 'Polygon':
        ee_geometry = ee.Geometry.Polygon(dict_item['geometry']['coordinates'])
    if dict_item['geometry']['type'] == 'MultiPolygon':
        ee_geometry = ee.Geometry.MultiPolygon(dict_item['geometry']['coordinates'])
    if dict_item['geometry']['type'] == 'LineString':
        ee_geometry = ee.Geometry.LineString(dict_item['geometry']['coordinates'])
    if dict_item['geometry']['type'] == 'Point':
        ee_geometry = ee.Geometry.Point(dict_item['geometry']['coordinates'])
    
    features.append(ee.Feature(ee_geometry))

    return ee.FeatureCollection(features)

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