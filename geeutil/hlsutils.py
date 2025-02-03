import ee 

def add_cloud_band(image):
    # define bit_masks
    shadow_bit_mask = (1 << 3)
    cloud_bit_mask = (1 << 1)
    dcloudBitMask = (1 << 2)
    # get Fmask image band
    fmask = image.select('Fmask')

    # define mask
    cloud = fmask.bitwiseAnd(shadow_bit_mask).eq(0) \
        .And(fmask.bitwiseAnd(cloud_bit_mask).eq(0)) \
        .And(fmask.bitwiseAnd(dcloudBitMask).eq(0)).Not().rename('clouds')
        
    return image.addBands(ee.Image([cloud]))