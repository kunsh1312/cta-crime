#Import relevant packages and setting PATH
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely import Point

user_path = Path(__file__).parent.resolve()
raw_data_path = user_path.parent/ "data" / "raw-data" 
derived_data_path = user_path.parent/ "data" / "derived-data"

#Loading all datasets
df_crime = pd.read_csv(raw_data_path / "Crimes_-_2001_to_Present_20260218.csv")
df_ridership = pd.read_csv(raw_data_path / "CTA_Ridership_L_Station_Entries_Daily_Totals_2022-2026.csv")
gdf_station = gpd.read_file(raw_data_path / "CTA_RailStations/CTA_RailStations.shp")
gdf_lines = gpd.read_file(raw_data_path / "CTA_RailLines/CTA_RailLines.shp")

#Adding missing Dame-Lake station which was opened in 2024 while data is from 2023 
gdf_station.set_crs("EPSG:3435",inplace=True)
gdf_station.to_crs("EPSG:4326",inplace=True)
new_row = gpd.GeoDataFrame({
    'STATION_ID': [1710],
    'LONGNAME': ['Damen-Lake'],
    'LINES': ['Green Line'],
    'ADDRESS': ['N Damen Ave & W Lake St'],
    'ADA': [1],
    'PKNRD': [0]
}, geometry=[Point(-87.676800, 41.885011)], crs="EPSG:4326")
gdf_station = pd.concat([gdf_station, new_row], ignore_index=True)
gdf_station.to_crs("EPSG:3435",inplace=True)

#Drop Roosevent/Wabash as ridership data combines them under one station called roosevelt 
#with one being elevated and the other being a subway but both are at the same location
gdf_station = gdf_station[gdf_station["LONGNAME"]!="Roosevelt/Wabash"]

#Converting crime to gdf with lattitude longitude crs then setting to same crs as other gdfs
gdf_crime = gpd.GeoDataFrame(
    df_crime,
    geometry = gpd.points_from_xy(df_crime.Longitude, df_crime.Latitude),
    crs = "EPSG:4326"
) 
gdf_crime.to_crs("EPSG:3435",inplace=True)

#subsetting all CTA crimes to only include those happening on a train
location_types = gdf_crime["Location Description"].unique().tolist()
CTA_types = [item for item in location_types if isinstance(item, str) and "CTA" in item]
items_to_remove = ['CTA PARKING LOT / GARAGE / OTHER PROPERTY','CTA TRACKS - RIGHT OF WAY','CTA PROPERTY','CTA BUS STOP','CTA BUS','CTA PLATFORM',
 'CTA STATION', 'CTA "L" PLATFORM','CTA SUBWAY STATION']
CTA_types = [item for item in CTA_types if item not in items_to_remove]
gdf_crime_CTA_lines = gdf_crime[gdf_crime["Location Description"].isin(CTA_types)]
gdf_crime_CTA_lines = gdf_crime_CTA_lines[
    (gdf_crime_CTA_lines.geometry.x > 1) | (gdf_crime_CTA_lines.geometry.y > 1)
]

#creating Line crimes gdf to filter crimes that dont happen within certain distance of a train line to ensure reasonability
gdf_C_by_L = gpd.sjoin_nearest(
    left_df= gdf_crime_CTA_lines, 
    right_df= gdf_lines, 
    how="inner",
    max_distance=1500, #approx 450 metres, 457.2
)
gdf_C_by_L.drop_duplicates(subset=["ID"],keep="first")
gdf_C_by_L.drop(columns=['LINES', 'DESCRIPTIO', 'TYPE', 'LEGEND', 'SHAPE_LEN','index_right'],inplace=True)

#Linking crimes close to a line to their nearest station
gdf_C_by_L = gpd.sjoin_nearest(
    left_df= gdf_C_by_L, 
    right_df= gdf_station, 
    how="inner", #No max distance as these are already checked for reasonability due to being close to a line
    distance_col="distance_to_station"
)
gdf_C_by_L.drop_duplicates(subset=["ID"],keep="first",inplace=True)

#Now subsetting to include those crimes that happen at a train station
CTA_types = [item for item in location_types if isinstance(item, str) and "CTA" in item]
items_to_remove_2 = ['CTA PARKING LOT / GARAGE / OTHER PROPERTY','CTA TRACKS - RIGHT OF WAY','CTA PROPERTY','CTA BUS STOP','CTA BUS','CTA "L" TRAIN', 'CTA TRAIN']
CTA_types = [item for item in CTA_types if item not in items_to_remove_2]
gdf_crime_CTA_station = gdf_crime[gdf_crime["Location Description"].isin(CTA_types)]
gdf_crime_CTA_station = gdf_crime_CTA_station[
    (gdf_crime_CTA_station.geometry.x > 1) | (gdf_crime_CTA_station.geometry.y > 1)
]

#Link crimes to nearest station
gdf_C_by_S = gpd.sjoin_nearest(
    left_df= gdf_crime_CTA_station, 
    right_df= gdf_station, 
    how="inner",
    max_distance=1500, #approx 450 metres, 457.2
    distance_col="distance_to_station"
)
gdf_C_by_S.drop_duplicates(subset=["ID"],keep="first",inplace=True)
gdf_C_by_S

#Link any non CTA station/line crimes happening within a smaller radius of the station to the nearest station.
items_to_remove_3 = ['CTA "L" TRAIN', 'CTA TRAIN','CTA PLATFORM','CTA STATION', 'CTA "L" PLATFORM','CTA SUBWAY STATION']
other_location = [item for item in location_types if item not in items_to_remove_3]
gdf_crime_other = gdf_crime[gdf_crime["Location Description"].isin(other_location)]
gdf_OC_by_S = gpd.sjoin_nearest(
    left_df= gdf_crime_other, 
    right_df= gdf_station, 
    how="inner",
    max_distance=700, #approx 200 metres, 213.36
    distance_col="distance_to_station"
)
gdf_OC_by_S.drop_duplicates(subset=["ID"],keep="first",inplace=True)
gdf_OC_by_S

#Concatenating all 3 datasets to get relevant crime dataset with associated station data and save to derived data
gdf_crime_combo = pd.concat([gdf_C_by_L,gdf_C_by_S,gdf_OC_by_S])
gdf_crime_combo.drop_duplicates(subset=["ID"],keep="first",inplace=True)

#preparing ridership data and crime to be merged 
df_ridership["rides"] = df_ridership["rides"].str.replace(',', '').astype(int)
df_ridership["date"]
df_ridership['date'] = pd.to_datetime(df_ridership['date'])
df_ridership["Year"] = df_ridership["date"].dt.year
df_ridership["Month"] = df_ridership["date"].dt.month
gdf_crime_combo["Date"] = pd.to_datetime(gdf_crime_combo["Date"]).dt.date
gdf_crime_combo["Date"] = pd.to_datetime(gdf_crime_combo["Date"])
gdf_crime_combo = gdf_crime_combo[gdf_crime_combo['Date'] <= (df_ridership['date'].max())] #ridership data ends before crime data
damen_date = df_ridership[df_ridership['stationname']=='Damen-Lake']['date'].min()
gdf_crime_combo = gdf_crime_combo[(gdf_crime_combo["LONGNAME"]!="Damen-Lake") | (gdf_crime_combo["Date"]>=damen_date)]

df_ridership['Year'].value_counts()


#renaming stations whose names dont match between datasets
station_mapping = {
    'Addison-Ravenswood': 'Addison-Brown',
    'Ashland-Midway': 'Ashland-Orange',
    'Austin-Congress': 'Austin-Forest Park',
    'California-Douglas': 'California-Cermak',
    'Cicero-Congress': 'Cicero-Forest Park',
    'Cicero-Douglas': 'Cicero-Cermak',
    'Clinton-Congress': 'Clinton-Forest Park',
    'Conservatory-Central Park': 'Conservatory',
    'Cottage Grove': 'East 63rd-Cottage Grove',
    'Damen': 'Damen-Cermak',
    'Damen-Ravenswood': 'Damen-Brown',
    'Halsted-Midway': 'Halsted-Orange',
    'Harlem-Congress': 'Harlem-Forest Park',
    'Illinois Medical District': 'Medical Center',
    'Irving Park-Ravenswood': 'Irving Park-Brown',
    'Kedzie-Douglas': 'Kedzie-Cermak',
    'Kedzie-Homan': 'Kedzie-Homan-Forest Park',
    'Kedzie-Ravenswood': 'Kedzie-Brown',
    'Montrose-Ravenswood': 'Montrose-Brown',
    'Morgan': 'Morgan-Lake',
    'Oak Park-Congress': 'Oak Park-Forest Park',
    'Pulaski-Congress': 'Pulaski-Forest Park',
    'Pulaski-Douglas': 'Pulaski-Cermak',
    'Pulaski-Midway': 'Pulaski-Orange',
    'Roosevelt/State': 'Roosevelt',
    'Western-Congress': 'Western-Forest Park',
    'Western-Douglas': 'Western-Cermak',
    'Western-Midway': 'Western-Orange',
    'Western-Ravenswood': 'Western-Brown'
}

gdf_crime_combo['LONGNAME'] = gdf_crime_combo['LONGNAME'].replace(station_mapping)
gdf_station['LONGNAME'] = gdf_station['LONGNAME'].replace(station_mapping)

#Merge crime derived with ridership data. left merge to preserve ridership data for dates and stations with no crime data
#Drop geometry from crime_combo and add it to ridership ensure every observation has a geometry
gdf_crime_combo.drop(columns=["geometry"],inplace=True)
df_ridership_geo = pd.merge(left=df_ridership,right=gdf_station,how="outer",left_on=["stationname"],right_on=["LONGNAME"])
gdf_crime_derived = pd.merge(left=df_ridership_geo,right=gdf_crime_combo,how="outer",left_on=["stationname","date"],right_on=["LONGNAME","Date"],indicator=True)

#Drop those stations which have no crime data. Maybe due to falling outside of CPD's remit
a = gdf_crime_combo["LONGNAME"].unique().tolist()
b= gdf_station['LONGNAME'].unique().tolist()
difference_list1_not_in_list2 = list(set(b) - set(a))
gdf_crime_derived = gdf_crime_derived[~gdf_crime_derived["stationname"].isin(difference_list1_not_in_list2)]
gdf_crime_derived["_merge"].value_counts()

#Turn derived crime into geodataframe and save
gdf_crime_derived = gpd.GeoDataFrame(gdf_crime_derived, geometry='geometry')
gdf_crime_derived.set_crs("EPSG:3435",inplace=True)
gdf_crime_derived.to_file(derived_data_path / "derived_crime.shp",driver = 'ESRI Shapefile')









