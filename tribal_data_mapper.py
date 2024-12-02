import json
import folium
import pandas as pd
from typing import List, Dict, Any
import branca.colormap as cm

class TribalDataMapper:
    def __init__(self, geojson_path: str):
        """Initialize the mapper with the GeoJSON file path."""
        with open(geojson_path, 'r') as f:
            self.data = json.load(f)
        
        # Convert to pandas DataFrame for easier filtering
        self.df = self._convert_to_dataframe()
        
        # Define PNW regions (Northwest region in BIA classification)
        self.pnw_region = ['Northwest']
        
        # Initialize custom tribes list
        self.custom_tribes = set()
        
    def _convert_to_dataframe(self) -> pd.DataFrame:
        """Convert GeoJSON features to pandas DataFrame."""
        records = []
        for feature in self.data['features']:
            record = feature['properties'].copy()
            record['longitude'] = feature['geometry']['coordinates'][0]
            record['latitude'] = feature['geometry']['coordinates'][1]
            records.append(record)
        return pd.DataFrame(records)
    
    def add_custom_tribe(self, tribe_name: str) -> bool:
        """Add a specific tribe to the custom tribes list."""
        # Search for the tribe in the DataFrame
        tribe_data = self.df[self.df['tribefullname'].str.contains(tribe_name, case=False, na=False)]
        if len(tribe_data) > 0:
            self.custom_tribes.add(tribe_name.lower())
            return True
        return False
    
    def remove_custom_tribe(self, tribe_name: str) -> bool:
        """Remove a specific tribe from the custom tribes list."""
        if tribe_name.lower() in self.custom_tribes:
            self.custom_tribes.remove(tribe_name.lower())
            return True
        return False
    
    def get_pnw_and_custom_tribes(self) -> pd.DataFrame:
        """Get tribes from PNW region and custom added tribes."""
        # Get PNW tribes
        pnw_tribes = self.df[self.df['biaregion'].isin(self.pnw_region)]
        
        # Get custom tribes
        custom_tribes_mask = self.df['tribefullname'].str.lower().apply(
            lambda x: any(tribe in x.lower() for tribe in self.custom_tribes)
        )
        custom_tribes_df = self.df[custom_tribes_mask]
        
        # Combine and remove duplicates
        combined_tribes = pd.concat([pnw_tribes, custom_tribes_df]).drop_duplicates()
        return combined_tribes
    
    def create_pnw_and_custom_map(self) -> folium.Map:
        """Create a map showing PNW tribes and custom added tribes with different colors."""
        # Get the combined data
        data = self.get_pnw_and_custom_tribes()
        
        # Calculate center
        center = [data['latitude'].mean(), data['longitude'].mean()]
        
        # Create the base map
        m = folium.Map(location=center, zoom_start=5)
        
        # Create different colored markers for PNW and custom tribes
        for _, row in data.iterrows():
            is_pnw = row['biaregion'] in self.pnw_region
            
            popup_html = f"""
                <b>{row['tribefullname']}</b><br>
                Region: {row['biaregion']}<br>
                Leader: {row['firstname']} {row['lastname']}<br>
                Title: {row['jobtitle']}<br>
                Phone: {row['phone']}<br>
                Email: {row['email']}<br>
                Type: {"PNW Region" if is_pnw else "Custom Added"}
            """
            
            # Use blue for PNW tribes, red for custom added tribes
            icon_color = 'blue' if is_pnw else 'red'
            
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=popup_html,
                tooltip=row['tribefullname'],
                icon=folium.Icon(color=icon_color, icon='info-sign')
            ).add_to(m)
            
        # Add a legend
        legend_html = '''
             <div style="position: fixed; 
                         bottom: 50px; right: 50px; width: 150px; height: 90px; 
                         border:2px solid grey; z-index:9999; font-size:14px;
                         background-color:white;
                         padding: 10px;
                         border-radius: 5px;
                         ">
             <p><i class="fa fa-map-marker fa-2x" style="color:blue"></i> PNW Region</p>
             <p><i class="fa fa-map-marker fa-2x" style="color:red"></i> Custom Added</p>
             </div>
             '''
        m.get_root().html.add_child(folium.Element(legend_html))
            
        return m
    
    def list_all_tribes(self) -> pd.DataFrame:
        """Return a sorted list of all tribes with their regions."""
        return self.df[['tribefullname', 'biaregion']].sort_values('tribefullname')
    
    def save_map(self, map_object: folium.Map, output_path: str):
        """Save the map to an HTML file."""
        map_object.save(output_path)

# Example usage:
if __name__ == "__main__":
    # Initialize the mapper
    mapper = TribalDataMapper("bia_tribal_leaders_sources/geoJSON_TribalLeadership_Directory_3002994166247985726.geojson")
    
    # Add some example custom tribes
    mapper.add_custom_tribe("Standing Rock Sioux")
    mapper.add_custom_tribe("Fort Sill Apache")
    
    # Create and save the PNW + custom tribes map
    custom_map = mapper.create_pnw_and_custom_map()
    mapper.save_map(custom_map, "pnw_and_custom_tribes_map.html")
    
    # Print all tribes for reference
    print("\nAll tribes and their regions:")
    print(mapper.list_all_tribes().to_string())
