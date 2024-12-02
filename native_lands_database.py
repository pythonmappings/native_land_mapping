import duckdb
import json
import pandas as pd
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

class NativeLandsDatabase:
    def __init__(self, db_path: str = "native_lands.duckdb"):
        """Initialize the database connection and create tables if they don't exist."""
        self.conn = duckdb.connect(db_path)
        self._initialize_database()
    
    def _initialize_database(self):
        """Create the necessary tables if they don't exist."""
        # BIA Tribes table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bia_tribes (
                tribe_id INTEGER,
                tribe_full_name VARCHAR,
                tribe_name VARCHAR,
                tribe_alternate_name VARCHAR,
                bia_region VARCHAR,
                latitude DOUBLE,
                longitude DOUBLE,
                leader_name VARCHAR,
                leader_title VARCHAR,
                phone VARCHAR,
                email VARCHAR,
                website VARCHAR,
                PRIMARY KEY (tribe_id)
            )
        """)
        
        # Native-Land.ca territories
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS native_land_territories (
                territory_id VARCHAR,
                name VARCHAR,
                description TEXT,
                geometry JSON,
                PRIMARY KEY (territory_id)
            )
        """)
        
        # Native-Land.ca languages
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS native_land_languages (
                language_id VARCHAR,
                name VARCHAR,
                description TEXT,
                geometry JSON,
                PRIMARY KEY (language_id)
            )
        """)
        
        # Native-Land.ca treaties
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS native_land_treaties (
                treaty_id VARCHAR,
                name VARCHAR,
                description TEXT,
                geometry JSON,
                PRIMARY KEY (treaty_id)
            )
        """)
        
        # Facilities table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                facility_id INTEGER,
                name VARCHAR,
                address VARCHAR,
                city VARCHAR,
                state VARCHAR,
                zip VARCHAR,
                latitude DOUBLE,
                longitude DOUBLE,
                PRIMARY KEY (facility_id)
            )
        """)
        
        # ERG Members and their tribal affiliations
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS erg_members (
                member_id INTEGER,
                name VARCHAR,
                tribe_id INTEGER,
                notes TEXT,
                PRIMARY KEY (member_id),
                FOREIGN KEY (tribe_id) REFERENCES bia_tribes(tribe_id)
            )
        """)
        
        # Cross-reference between BIA tribes and Native-Land.ca territories
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tribe_territory_mapping (
                tribe_id INTEGER,
                territory_id VARCHAR,
                confidence FLOAT,
                notes TEXT,
                FOREIGN KEY (tribe_id) REFERENCES bia_tribes(tribe_id),
                FOREIGN KEY (territory_id) REFERENCES native_land_territories(territory_id)
            )
        """)
    
    def import_bia_data(self, geojson_path: str):
        """Import BIA tribal data from GeoJSON file."""
        with open(geojson_path, 'r') as f:
            data = json.load(f)
        
        records = []
        for feature in data['features']:
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            
            record = {
                'tribe_id': feature['id'],
                'tribe_full_name': props['tribefullname'],
                'tribe_name': props['tribe'],
                'tribe_alternate_name': props['tribealternatename'],
                'bia_region': props['biaregion'],
                'latitude': coords[1],
                'longitude': coords[0],
                'leader_name': f"{props['firstname']} {props['lastname']}".strip(),
                'leader_title': props['jobtitle'],
                'phone': props['phone'],
                'email': props['email'],
                'website': props['website']
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        self.conn.execute("DELETE FROM bia_tribes")  # Clear existing data
        self.conn.execute("INSERT INTO bia_tribes SELECT * FROM df")
    
    def query_native_land_api(self, lat: float, lon: float) -> Dict[str, Any]:
        """Query the Native-Land.ca API for a specific location."""
        url = f"https://native-land.ca/api/index.php?maps=territories,languages,treaties&position={lat},{lon}"
        response = requests.get(url)
        return response.json() if response.status_code == 200 else None
    
    def add_facility(self, name: str, address: str, city: str, state: str, zip_code: str,
                    latitude: float, longitude: float) -> int:
        """Add a facility and automatically query Native-Land.ca API for its location."""
        # Insert facility
        facility_id = self.conn.execute("""
            INSERT INTO facilities (name, address, city, state, zip, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING facility_id
        """, (name, address, city, state, zip_code, latitude, longitude)).fetchone()[0]
        
        # Query Native-Land.ca API
        native_land_data = self.query_native_land_api(latitude, longitude)
        if native_land_data:
            # Store the results (you'll need to implement this based on your needs)
            pass
        
        return facility_id
    
    def add_erg_member(self, name: str, tribe_name: str, notes: Optional[str] = None) -> int:
        """Add an ERG member and their tribal affiliation."""
        # Find tribe_id from tribe_name
        result = self.conn.execute("""
            SELECT tribe_id FROM bia_tribes 
            WHERE tribe_full_name ILIKE ? OR tribe_name ILIKE ?
        """, (f"%{tribe_name}%", f"%{tribe_name}%")).fetchone()
        
        if not result:
            raise ValueError(f"Tribe not found: {tribe_name}")
        
        tribe_id = result[0]
        
        # Insert ERG member
        member_id = self.conn.execute("""
            INSERT INTO erg_members (name, tribe_id, notes)
            VALUES (?, ?, ?)
            RETURNING member_id
        """, (name, tribe_id, notes)).fetchone()[0]
        
        return member_id
    
    def get_facility_tribal_lands(self, facility_id: int) -> Dict[str, Any]:
        """Get all tribal lands information for a facility."""
        facility = self.conn.execute("""
            SELECT latitude, longitude FROM facilities WHERE facility_id = ?
        """, (facility_id,)).fetchone()
        
        if not facility:
            raise ValueError(f"Facility not found: {facility_id}")
        
        return self.query_native_land_api(facility[0], facility[1])
    
    def close(self):
        """Close the database connection."""
        self.conn.close()

# Example usage:
if __name__ == "__main__":
    db = NativeLandsDatabase()
    
    # Import BIA data
    db.import_bia_data("bia_tribal_leaders_sources/geoJSON_TribalLeadership_Directory_3002994166247985726.geojson")
    
    # Example: Add a facility
    facility_id = db.add_facility(
        name="Example Hospital",
        address="123 Main St",
        city="Portland",
        state="OR",
        zip_code="97201",
        latitude=45.5155,
        longitude=-122.6789
    )
    
    # Example: Add an ERG member
    member_id = db.add_erg_member(
        name="John Doe",
        tribe_name="Confederated Tribes of the Umatilla Indian Reservation",
        notes="Member since 2023"
    )
    
    # Get tribal lands for a facility
    tribal_lands = db.get_facility_tribal_lands(facility_id)
    print(f"Facility {facility_id} is on these tribal lands:", tribal_lands)
    
    db.close()
