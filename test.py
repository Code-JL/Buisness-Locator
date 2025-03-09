import time
import pandas as pd
from geopy.geocoders import Nominatim
import pgeocode
from tabulate import tabulate

def get_coords_nominatim(country_code, postal_code):
    """Get coordinates using geopy's Nominatim service"""
    start_time = time.time()
    geolocator = Nominatim(user_agent="PostalCodeTest")
    query = f"{postal_code}, {country_code}"
    
    try:
        # Add delay to respect usage policy
        location = geolocator.geocode(query)
        
        if location:
            duration = time.time() - start_time
            return location.latitude, location.longitude, duration
        else:
            duration = time.time() - start_time
            return None, None, duration
    except Exception as e:
        duration = time.time() - start_time
        print(f"Nominatim error for {postal_code}, {country_code}: {e}")
        return None, None, duration

def get_coords_pgeocode(country_code, postal_code):
    """Get coordinates using pgeocode library"""
    start_time = time.time()
    try:
        nomi = pgeocode.Nominatim(country_code)
        result = nomi.query_postal_code(postal_code)
        
        duration = time.time() - start_time
        if not result.empty and not pd.isna(result['latitude']) and not pd.isna(result['longitude']):
            return result['latitude'], result['longitude'], duration
        else:
            return None, None, duration
    except Exception as e:
        duration = time.time() - start_time
        print(f"pgeocode error for {postal_code}, {country_code}: {e}")
        return None, None, duration

def test_postal_codes():
    # Test cases - postal codes from US and Canada
    test_cases = [
        # US urban areas
        {"country": "US", "postal": "10001", "description": "New York, NY (Manhattan)"},
        {"country": "US", "postal": "90210", "description": "Beverly Hills, CA"},
        {"country": "US", "postal": "60601", "description": "Chicago, IL (Downtown)"},
        
        # US rural areas
        {"country": "US", "postal": "59223", "description": "Flaxville, MT (Rural)"},
        {"country": "US", "postal": "67950", "description": "Elkhart, KS (Rural)"},
        
        # Canadian urban areas
        {"country": "CA", "postal": "M5V 2H1", "description": "Toronto, ON (CN Tower)"},
        {"country": "CA", "postal": "H2Y 1C6", "description": "Montreal, QC (Old Port)"},
        {"country": "CA", "postal": "V6C 2T1", "description": "Vancouver, BC (Downtown)"},
        
        # Canadian rural areas
        {"country": "CA", "postal": "A0P 1A0", "description": "Tilting, NL (Rural)"},
        {"country": "CA", "postal": "Y0B 1N0", "description": "Old Crow, YT (Remote)"},
        
        # Format variations
        {"country": "CA", "postal": "M5V2H1", "description": "Toronto (no space)"},
        {"country": "US", "postal": "90210-1234", "description": "Beverly Hills with +4"},
    ]
    
    results = []
    
    # Process each test case
    for case in test_cases:
        country = case["country"]
        postal = case["postal"]
        description = case["description"]
        
        print(f"Testing {postal}, {country} ({description})...")
        
        # Get coordinates using both methods
        # Add a pause between Nominatim requests to avoid rate limiting
        pgeo_lat, pgeo_lng, pgeo_time = get_coords_pgeocode(country, postal)
        
        time.sleep(1.5)  # Respect Nominatim usage policy
        nom_lat, nom_lng, nom_time = get_coords_nominatim(country, postal)
        
        # Distance calculation (if both returned results)
        distance = "N/A"
        if pgeo_lat and nom_lat:
            # Very simple distance calculation (not accounting for Earth's curvature)
            # This is just to show relative differences, not accurate distances
            dlat = abs(pgeo_lat - nom_lat)
            dlng = abs(pgeo_lng - nom_lng)
            distance = f"{((dlat**2 + dlng**2)**0.5):.6f}°"
        
        # Add to results
        results.append({
            "Country": country,
            "Postal": postal,
            "Description": description,
            "pgeocode Lat": f"{pgeo_lat:.6f}" if pgeo_lat else "Not found",
            "pgeocode Lng": f"{pgeo_lng:.6f}" if pgeo_lng else "Not found",
            "pgeocode Time": f"{pgeo_time:.3f}s",
            "Nominatim Lat": f"{nom_lat:.6f}" if nom_lat else "Not found",
            "Nominatim Lng": f"{nom_lng:.6f}" if nom_lng else "Not found",
            "Nominatim Time": f"{nom_time:.3f}s",
            "Difference": distance
        })
    
    # Display results in a table
    print("\n\n" + "="*100)
    print("POSTAL CODE GEOCODING COMPARISON: PGEOCODE VS NOMINATIM")
    print("="*100 + "\n")
    
    # Create a more readable table structure
    table_data = []
    for r in results:
        table_data.append([
            f"{r['Country']}: {r['Postal']}",
            r['Description'],
            f"{r['pgeocode Lat']}\n{r['pgeocode Lng']}",
            f"{r['Nominatim Lat']}\n{r['Nominatim Lng']}",
            r['Difference'],
            f"{r['pgeocode Time']} / {r['Nominatim Time']}"
        ])
    
    headers = [
        "Postal Code", 
        "Description", 
        "pgeocode Coords", 
        "Nominatim Coords", 
        "Difference", 
        "Time (pg/nom)"
    ]
    
    from tabulate import tabulate
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Summary statistics
    pgeo_success = sum(1 for r in results if "Not found" not in r["pgeocode Lat"])
    nom_success = sum(1 for r in results if "Not found" not in r["Nominatim Lat"])
    
    print(f"\nSummary:")
    print(f"- pgeocode success rate: {pgeo_success}/{len(results)} ({pgeo_success/len(results)*100:.1f}%)")
    print(f"- Nominatim success rate: {nom_success}/{len(results)} ({nom_success/len(results)*100:.1f}%)")
    
    # Calculate average times
    pgeo_times = [float(r["pgeocode Time"].replace("s", "")) for r in results]
    nom_times = [float(r["Nominatim Time"].replace("s", "")) for r in results]
    
    print(f"- Average pgeocode time: {sum(pgeo_times)/len(pgeo_times):.3f}s")
    print(f"- Average Nominatim time: {sum(nom_times)/len(nom_times):.3f}s")

if __name__ == "__main__":
    # Check if requirements are installed
    try:
        import tabulate
    except ImportError:
        print("Please install required packages:")
        print("pip install geopy pgeocode pandas tabulate")
        exit(1)
        
    test_postal_codes()