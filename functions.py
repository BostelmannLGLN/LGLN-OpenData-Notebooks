import geopandas as gpd
from tqdm import tqdm
import requests
import pandas as pd
import fnmatch
from datetime import timedelta

def select_tiles_in_bbox_of_area(tiles, area):
    bounds = area.total_bounds
    left = bounds[0]
    bottom = bounds[1]
    right = bounds[2]
    top = bounds[3]
    selected_tiles = tiles.cx[left:right, bottom:top]
    return selected_tiles

        
def load_tiles(region=None, landkreis=None, RD=None, be_nrs=None, cx=None, print_list=False, use_cos=False):
    
    name = None
    selected_area = None
    selected_tiles = None
    
    if region:
        if region == 'NI':
            be_name = 'be8_nr'
            
            if use_cos:
                tiles = gpd.read_file('https://cloud.code-de.org:8080/swift/v1/AUTH_622a231224cb46c6982643e55e817c98/geojson/BE8_in_NI.geojson')
                ni = gpd.read_file('https://cloud.code-de.org:8080/swift/v1/AUTH_622a231224cb46c6982643e55e817c98/geojson/NI.geojson')
            else: #read from local dat folder
                tiles = gpd.read_file('data/BE8_in_NI.geojson')
                ni = gpd.read_file('./data/NI.geojson')
                RDs = gpd.read_file('./data/RDs.geojson')

            if print_list:
                print(ni.BEZ_KRS.unique())
                print(RDs.RD.unique())
            if landkreis:
                name = landkreis
                selected_area = ni.loc[ni.BEZ_KRS == landkreis]
            elif RD:
                name = RD
                selected_area = RDs.loc[RDs.RD == RD]
            else:
                name = 'Niedersachsen'
                selected_area = ni # ganz Niedersachsen


        if region == 'LHH':
            tiles = gpd.read_file('data/BE8_in_NI.geojson')
            be_name = 'be8_nr'

            LHH = gpd.read_file('../data/geojson/SKH20_Stadtgrenze.geojson')
            name = 'Hannover'
            selected_area = LHH.loc[LHH.GEMEINDE == name]


        if region == 'SH':
            tiles = gpd.read_file('data/BE6_in_SH.geojson')
            be_name = 'be6_nr'

            sh = gpd.read_file('./data/SH.geojson')
            if print_list:
                print(sh.BEZ_KRS.unique())
            if landkreis:
                name = landkreis
                selected_area = sh.loc[sh.BEZ_KRS == name]
            else:
                name = 'Schleswig-Holstein'
                selected_area = sh

        if region == 'HE':
            tiles = gpd.read_file('data/BE8_Hessen.geojson')
            be_name = 'be8_nr'

            he = gpd.read_file('./data/Hessen.geojson')
            name = 'Hessen'
            selected_area = hessen

        if region == 'HH':
            tiles = gpd.read_file('data/BE8_in_HH.geojson')
            be_name = 'be8_nr'

            #de = gpd.read_file('./data/DE.geojson')
            name = 'Hamburg'
            #selected_area = de.loc[de.GEN == name]
            # remove islands
            #multi_ploygon = selected_area.geometry
            #selected_area.geometry = [list(multi_ploygon[0])[0]]
            
            hh = gpd.read_file('./data/Hamburg.geojson')
            selected_area = hh
            
        tiles['nr'] = tiles[be_name]
        tiles.set_index('nr', inplace=True)        
        selected_tiles = select_tiles_in_bbox_of_area(tiles, selected_area)
    
    if cx or be_nrs:
        tiles = gpd.read_file('data/BE8_Norden.geojson')
        be_name = 'be8_nr'
        tiles['nr'] = tiles[be_name]
        tiles.set_index('nr', inplace=True)  
        name = 'Sentinel-2'
        if cx:
            left=cx[0]
            right=cx[1]
            bottom=cx[2]
            top=cx[3]
            selected_tiles = tiles.cx[left:right, bottom:top]
            selected_area = selected_tiles
        if be_nrs:
            selected_tiles = tiles.loc[be_nrs]
            selected_area = selected_tiles
            

        
    return name, be_name, selected_area, selected_tiles


def get_dates_from_list(image_list):
    dates = []
    for file_name in image_list:
        dates.append(file_name.split('_')[-3]) # TODO Warnin. mosaic name must have _
    return dates


def available_dates(selected_tiles, date_str, bucket):
    all_dates = []
    tiles_count = 0
    
    for tile_nr in tqdm(selected_tiles.index, desc=f'Lade Kacheln für {date_str}'):
    
        # Get content from bucket
        prefix = f'{tile_nr}/S2/{date_str}'
        request_url = bucket['endpoint_url'] + bucket['name'] + f'/?prefix={prefix}&format=json'
        json_response = requests.get(request_url)
        content = pd.read_json(json_response.content)

        # Get available dates from file names in bucket
        if len(content):
            objects_in_bucket = content.name.to_list()

            pattern = f'{tile_nr}/S2/{date_str}*/{tile_nr}_S2_{date_str}*_TCI_10m.tif'
            image_list = fnmatch.filter(objects_in_bucket, pattern)
            dates = get_dates_from_list(image_list)
            all_dates = all_dates + list(set(dates) - set(all_dates))

        else:
            dates = []
            
        selected_tiles.at[tile_nr, 'S2'] = int(len(dates))
        tiles_count = tiles_count + int(len(dates))
        
    all_dates = sorted(all_dates)
    
    return selected_tiles, all_dates, tiles_count


