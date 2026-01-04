"""
Helpers to define Balıkesir city center (Karesi + Altıeylül) polygon.
This is used to restrict all analysis to the true city center.
"""
import osmnx as ox
from shapely.ops import unary_union


def get_balikesir_center_polygon():
    """
    Returns a Shapely Polygon/MultiPolygon representing
    Karesi + Altıeylül (Balıkesir city center).
    """
    places = ["Karesi, Balıkesir, Türkiye", "Altıeylül, Balıkesir, Türkiye"]
    gdfs = [ox.geocode_to_gdf(p).to_crs(4326) for p in places]
    center_poly = unary_union([g.geometry.iloc[0] for g in gdfs])
    return center_poly


