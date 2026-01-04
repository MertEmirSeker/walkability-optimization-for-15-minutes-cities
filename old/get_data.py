# get_data_balikesir.py
# pip install osmnx geopandas shapely networkx

import os
import osmnx as ox
import geopandas as gpd
from shapely.ops import unary_union

# --- OSMnx ayarları ---
ox.settings.request_timeout = 180
ox.settings.overpass_rate_limit = True
ox.settings.use_cache = True
ox.settings.headers = {"User-Agent": "Balikesir-WALKOPT/1.0 (you@example.com)"}

# --- Balıkesir merkez: Karesi + Altıeylül ---
PLACES = ["Karesi, Balıkesir, Türkiye", "Altıeylül, Balıkesir, Türkiye"]
gdfs = [ox.geocode_to_gdf(p).to_crs(4326) for p in PLACES]
center_poly = unary_union([g.geometry.iloc[0] for g in gdfs])

out_dir = "out_balikesir_center"
os.makedirs(out_dir, exist_ok=True)

# --- 0) Merkezdeki mahalleleri (admin_level=10) indir ---
mahalle_tags = {"boundary": "administrative", "admin_level": "10"}
mahalle = ox.features_from_polygon(center_poly, tags=mahalle_tags)

# 0.a) Geometrisi boş olmayanları al
mahalle = mahalle[mahalle.geometry.notnull()].copy().to_crs(4326)

# 0.b) SADECE poligon geometrileri (overlay karışık tipe izin vermez)
mahalle = mahalle[mahalle.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

# 0.c) Geometri onarımı (self-intersection vb. için)
# Not: buffer(0) çok küçük topolojik hataları düzeltir
mahalle["geometry"] = mahalle.buffer(0)

# 0.d) Merkez poligonu ile kesişim
center_gdf = gpd.GeoDataFrame(geometry=[center_poly], crs=4326)
mahalle = gpd.overlay(mahalle, center_gdf, how="intersection")

# 0.e) Çok parçalı geometrileri satırlara ayır ve ufak kırıntıları ele
mahalle = mahalle.explode(index_parts=False).reset_index(drop=True)
m3857 = mahalle.to_crs(3857)
m3857["area_m2"] = m3857.area
mahalle = m3857[m3857["area_m2"] > 1000].to_crs(4326)

print("Mahalle sayısı:", len(mahalle))
mahalle.to_file(f"{out_dir}/balikesir_center_mahalle.geojson", driver="GeoJSON")

# --- 1) Yaya ağını indir (walk) ---
G_walk = ox.graph_from_polygon(center_poly, network_type="walk", simplify=True)
nodes_gdf, edges_gdf = ox.graph_to_gdfs(G_walk)

# --- 2) POI'ler (market, okul, restoran, cafe, bank, park vb.) ---
amenity_filter = {
    "shop": ["supermarket","convenience","grocer"],
    "amenity": ["school", "restaurant", "cafe", "bank"],
    "leisure": ["park", "pitch", "playground"]
}
pois = ox.features_from_polygon(center_poly, tags=amenity_filter)

# --- 3) Binalar (konut yoğunluğu vs.) ---
buildings = ox.features_from_polygon(center_poly, tags={"building": True})

# --- 4) Kaydet (GeoJSON) ---
edges_gdf.to_file(f"{out_dir}/balikesir_center_walk_edges.geojson", driver="GeoJSON")
nodes_gdf.to_file(f"{out_dir}/balikesir_center_walk_nodes.geojson", driver="GeoJSON")
pois.to_file(f"{out_dir}/balikesir_center_pois.geojson", driver="GeoJSON")
buildings.to_file(f"{out_dir}/balikesir_center_buildings.geojson", driver="GeoJSON")

print("✓ Balıkesir MERKEZ (Karesi+Altıeylül) verileri indirildi ve kaydedildi.")
