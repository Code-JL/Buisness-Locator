import osmnx as ox
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon, Point
import concurrent.futures
import os
import hashlib
import pickle
import time
from pathlib import Path
import math
import random
from functools import wraps

# Set OSMnx cache directory and configure using the updated API
# In newer versions of OSMnx, we use ox.settings instead of ox.config
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.cache_folder = './cache/osmnx'

# Define multiple Overpass API endpoints
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",  # Default endpoint
    "https://overpass.private.coffee/api/interpreter"  # Alternative endpoint
]

# Track endpoint status
endpoint_status = {endpoint: True for endpoint in OVERPASS_ENDPOINTS}
endpoint_last_used = {endpoint: 0 for endpoint in OVERPASS_ENDPOINTS}

def get_overpass_endpoint(worker_id=None):
    """
    Get an Overpass API endpoint based on availability and load balancing
    
    Args:
        worker_id: Optional worker ID for consistent endpoint selection in parallel processing
    
    Returns:
        str: URL of the Overpass API endpoint to use
    """
    # Filter to only working endpoints
    working_endpoints = [ep for ep in OVERPASS_ENDPOINTS if endpoint_status[ep]]
    
    # If no endpoints are working, reset all to try again
    if not working_endpoints:
        for ep in OVERPASS_ENDPOINTS:
            endpoint_status[ep] = True
        working_endpoints = OVERPASS_ENDPOINTS
    
    # If worker_id is provided (for parallel processing), use it for consistent endpoint selection
    if worker_id is not None:
        return working_endpoints[worker_id % len(working_endpoints)]
    
    # Otherwise select based on least recently used
    return min(working_endpoints, key=lambda ep: endpoint_last_used[ep])

def with_endpoint_fallback(func):
    """Decorator to retry a function with different endpoints if one fails"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try each endpoint
        errors = {}
        
        # Get worker ID if in parallel context
        worker_id = kwargs.pop('worker_id', None)
        
        # Try primary endpoint first
        primary_endpoint = get_overpass_endpoint(worker_id)
        endpoints_to_try = [primary_endpoint] + [ep for ep in OVERPASS_ENDPOINTS if ep != primary_endpoint]
        
        for endpoint in endpoints_to_try:
            # Skip endpoints marked as not working
            if not endpoint_status[endpoint]:
                continue
                
            try:
                # Set the endpoint for this attempt
                ox.settings.overpass_endpoint = endpoint
                endpoint_last_used[endpoint] = time.time()
                
                # Call the actual function
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Track the error
                errors[endpoint] = str(e)
                
                # Mark endpoint as not working if it's a connection issue
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    endpoint_status[endpoint] = False
                    print(f"Marking endpoint {endpoint} as unavailable due to: {str(e)}")
        
        # If we get here, all endpoints failed
        error_details = "; ".join([f"{ep}: {err}" for ep, err in errors.items()])
        raise Exception(f"All Overpass endpoints failed. Errors: {error_details}")
    
    return wrapper

@with_endpoint_fallback
def get_buildings_from_osm(latitude, longitude, tags, radius, timeout):
    """Wrapper for OSMnx's features_from_point with endpoint fallback"""
    return ox.features_from_point((latitude, longitude), tags, dist=radius)

def get_buildings_by_size(longitude, latitude, min_sqft=0, radius=500, timeout=180, use_cache=True, worker_id=None):
    """
    Get buildings of at least min_sqft within a radius of a point using OSMnx
    
    Parameters:
    -----------
    longitude : float
        Longitude coordinate
    latitude : float
        Latitude coordinate
    min_sqft : float
        Minimum building size in square feet to include
    radius : int
        Search radius in meters
    timeout : int
        Timeout for API in seconds (passed to OSMnx)
    use_cache : bool
        Whether to use local disk cache
    worker_id : int, optional
        Worker ID for parallel processing to assign consistent endpoints
    
    Returns:
    --------
    dict : Dictionary with buildings information (sqft, lat, lon)
    """
    # Create cache key from parameters
    cache_key = f"osmnx_{longitude}_{latitude}_{radius}_{min_sqft}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    cache_dir = Path("./cache")
    cache_file = cache_dir / f"buildings_{cache_hash}.pkl"
    
    # Check cache if enabled
    if use_cache and cache_file.exists():
        # Check if cache file is less than 24 hours old
        if time.time() - cache_file.stat().st_mtime < 86400:  # 24 hours
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                # Cache read failed, continue with API call
                pass
    
    try:
        # Set OSMnx timeout using the updated API
        ox.settings.timeout = timeout
        
        # Get buildings from OSM - point-based query with distance
        tags = {'building': True}
        
        try:
            # Use our wrapper function with endpoint fallback
            buildings_gdf = get_buildings_from_osm(latitude, longitude, tags, radius, timeout, worker_id=worker_id)
        except Exception as e:
            # Check specifically for the InsufficientResponseError
            if "No matching features" in str(e):
                print(f"No buildings found at ({latitude}, {longitude}) with radius {radius}m")
                return {"total_buildings": 0, "buildings": []}
            else:
                # Re-raise other errors
                raise
        
        # Handle empty response (this is now redundant but kept for robustness)
        if len(buildings_gdf) == 0:
            result = {"total_buildings": 0, "buildings": []}
            return result
        
        # Calculate accurate area by reprojecting to UTM
        utm_zone = int(((longitude + 180) / 6) % 60) + 1
        hemisphere = 'north' if latitude >= 0 else 'south'
        utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84 +units=m +no_defs"
        
        # Project to UTM for accurate area calculation
        buildings_utm = buildings_gdf.to_crs(utm_crs)
        
        # Calculate areas in square meters and square feet
        buildings_utm['area_m2'] = buildings_utm.geometry.area
        buildings_utm['area_sqft'] = buildings_utm['area_m2'] * 10.764
        
        # Calculate centroids
        buildings_utm['centroid'] = buildings_utm.geometry.centroid
        
        # Get the centroids back in WGS84
        centroids_wgs84 = buildings_utm['centroid'].to_crs('EPSG:4326')
        
        # Filter by minimum square footage
        buildings_filtered = buildings_utm[buildings_utm['area_sqft'] >= min_sqft].copy()
        
        # Format results
        building_results = []
        
        for idx, row in buildings_filtered.iterrows():
            # Get centroid in WGS84
            lon, lat = centroids_wgs84.loc[idx].x, centroids_wgs84.loc[idx].y
            
            # Extract tags
            tags = row.tags if hasattr(row, 'tags') else {}
            if isinstance(tags, str):
                import json
                try:
                    tags = json.loads(tags)
                except:
                    tags = {}
            
            # Extract address components
            address_components = {
                "housenumber": row.get('addr:housenumber', tags.get('addr:housenumber', '')),
                "street": row.get('addr:street', tags.get('addr:street', '')),
                "city": row.get('addr:city', tags.get('addr:city', '')),
                "postcode": row.get('addr:postcode', tags.get('addr:postcode', '')),
                "state": row.get('addr:state', tags.get('addr:state', '')),
                "country": row.get('addr:country', tags.get('addr:country', ''))
            }
            
            # Clean up NaN values in address components
            for key in address_components:
                # Convert to string and check for NaN values
                if isinstance(address_components[key], float) and np.isnan(address_components[key]):
                    address_components[key] = ""
                # Handle any other empty values or None
                if not address_components[key]:
                    address_components[key] = ""
            
            # Construct a formatted address string
            formatted_address = ""
            has_street_info = False

            if address_components["housenumber"] and address_components["street"]:
                formatted_address = f"{address_components['housenumber']} {address_components['street']}"
                has_street_info = True
            elif address_components["street"]:
                formatted_address = address_components["street"]
                has_street_info = True

            # Initialize address_parts as a list
            address_parts = []
            if formatted_address:
                address_parts.append(formatted_address)
            if address_components["city"]:
                address_parts.append(address_components["city"])
            if address_components["state"]:
                address_parts.append(address_components["state"])
            if address_components["postcode"]:
                address_parts.append(address_components["postcode"])

            # Make sure all parts are valid strings
            address_parts = [str(part) for part in address_parts if part and part != "nan"]

            # Set default if no address parts are available
            full_address = ", ".join(address_parts) if address_parts else "No address data"

            # Add a flag to indicate if this address is missing street information
            # This makes it easy to identify in the main app
            has_complete_address = has_street_info and address_components["city"]
            
            # Get building type and normalize "yes" to "nan"
            building_type = row.get('building', tags.get('building', 'unknown'))
            if str(building_type).lower() == "yes":
                building_type = "nan"
            
            building_info = {
                "id": idx[1] if isinstance(idx, tuple) else idx,  # OSM ID
                "sqft": round(float(row['area_sqft']), 2),
                "lat": lat,
                "lon": lon,
                "address": full_address,  # Add the formatted address
                "has_complete_address": has_complete_address,  # Add the flag
                "building_type": building_type,
                "name": row.get('name', tags.get('name', 'unnamed')),
                "levels": row.get('building:levels', tags.get('building:levels', 'unknown'))
            }
            
            building_results.append(building_info)
        
        # Sort by square footage (largest first)
        building_results.sort(key=lambda x: x["sqft"], reverse=True)
        
        result = {
            "total_buildings": len(building_results),
            "buildings": building_results
        }
        
        # Cache successful results
        if use_cache:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

def normalize_building_type(self, building_type):
    """Normalize building type values"""
    # Convert to string and lowercase for consistency
    building_type = str(building_type).lower()
    
    # Convert "yes" to "nan" as these are buildings without a specific type
    if building_type == "yes":
        return "nan"
    
    # Return the original type for all other cases
    return building_type

def process_large_area(longitude, latitude, min_sqft=0, radius=1000, max_radius_per_batch=1000):
    """
    Process large area searches more efficiently
    
    For OSMnx, we can handle larger areas directly, but still use quadrants
    for very large areas to avoid timeout issues
    """
    # For small and medium areas, use direct query
    if radius <= 2000:
        return get_buildings_by_size(longitude, latitude, min_sqft, radius)
    
    # For larger areas, split into quadrants
    return process_quadrants(longitude, latitude, min_sqft, radius)

def process_quadrant_worker(params_with_id):
    return get_buildings_by_size(*params_with_id[0], worker_id=params_with_id[1])

def process_quadrants(longitude, latitude, min_sqft=0, radius=5000):
    """Split a large area using process-based parallelism for CPU-bound tasks"""
    # Calculate the quadrant data
    quadrant_radius = radius / 2
    # Approximate conversion from meters to degrees at the equator
    degree_offset = quadrant_radius / 111320
    
    quadrants = [
        {"lon": longitude + degree_offset, "lat": latitude + degree_offset},
        {"lon": longitude - degree_offset, "lat": latitude + degree_offset},
        {"lon": longitude + degree_offset, "lat": latitude - degree_offset},
        {"lon": longitude - degree_offset, "lat": latitude - degree_offset}
    ]
    
    # Use ProcessPoolExecutor for better performance on CPU-bound tasks
    from concurrent.futures import ProcessPoolExecutor
    
    results = {"buildings": [], "total_buildings": 0}
    
    # Serialize the partial function arguments for multiprocessing
    args = [(q["lon"], q["lat"], min_sqft, quadrant_radius) for q in quadrants]
    
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 4)) as executor:
        # Pass worker_id to ensure consistent endpoint selection
        quadrant_results = list(executor.map(
            process_quadrant_worker, 
            [(args[i], i) for i in range(len(args))]
        ))
        
        for quadrant_result in quadrant_results:
            if "buildings" in quadrant_result:
                results["buildings"].extend(quadrant_result["buildings"])
                results["total_buildings"] += quadrant_result["total_buildings"]
    
    # Remove duplicate buildings (same ID)
    unique_buildings = {}
    for building in results["buildings"]:
        if building["id"] not in unique_buildings:
            unique_buildings[building["id"]] = building
    
    results["buildings"] = list(unique_buildings.values())
    results["total_buildings"] = len(results["buildings"])
    
    # Sort by square footage
    results["buildings"].sort(key=lambda x: x["sqft"], reverse=True)
    
    return results

# Keep the calculate_area_from_latlon function for compatibility
def calculate_area_from_latlon(polygon):
    """Calculate area using UTM projection"""
    lon, lat = polygon.centroid.x, polygon.centroid.y
    
    # Fast path for small polygons
    if polygon.bounds[2] - polygon.bounds[0] < 0.1 and polygon.bounds[3] - polygon.bounds[1] < 0.1:
        import pyproj
        from shapely.ops import transform
        
        proj = pyproj.Transformer.from_crs(
            "EPSG:4326",
            f"+proj=utm +zone={int(((lon + 180) / 6) % 60) + 1} +datum=WGS84 +units=m +no_defs",
            always_xy=True
        ).transform
        
        return transform(proj, polygon).area
    
    # Original method for larger polygons
    gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")
    utm_zone = int(((lon + 180) / 6) % 60) + 1
    hemisphere = 'north' if lat >= 0 else 'south'
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84 +units=m +no_defs"
    
    gdf_projected = gdf.to_crs(utm_crs)
    return gdf_projected.geometry[0].area

# Example usage
if __name__ == "__main__":
    # Example with the Empire State Building area
    longitude = -73.9857
    latitude = 40.7484
    min_sqft = 5000  # Minimum 5,000 sq ft
    radius = 500     # 500 meters radius
    
    print(f"Finding buildings with at least {min_sqft} sq ft within {radius}m of ({latitude}, {longitude})")
    
    # For smaller searches
    result = get_buildings_by_size(longitude, latitude, min_sqft, radius)
    
    # For larger searches
    # result = process_large_area(longitude, latitude, min_sqft, 2000)
    
    print(f"Found {result['total_buildings']} buildings")
    
    # Print the top 5 largest buildings
    for i, building in enumerate(result["buildings"][:5]):
        print(f"{i+1}. {building['sqft']} sq ft at ({building['lat']}, {building['lon']})")
        print(f"   Type: {building['building_type']}, Name: {building['name']}")
        print()