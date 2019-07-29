# Rupesh Jeyaram 
# Created July 17th, 2019

# This file handles all the code for the US SIF visualizations tab

import time                            # For timing
from datetime import date              # For date queries
from db_utils import *                 # For easier querying

from bokeh.models import LinearColorMapper          # For mapping values/colors
from bokeh.models import ColumnDataSource           # For holding data
from bokeh.palettes import Viridis256 as palette    # The map palette to use
from bokeh.palettes import Category10 as time_pltt  # Time srs palette to use
from bokeh.plotting import figure                   # For creating the map
from bokeh.events import Tap, SelectionGeometry     # For recognizing tap
from bokeh.layouts import row, column               # For arranging view in grid
from bokeh.models import ColorBar, FixedTicker      # For map's color bar
from bokeh.models import DateRangeSlider            # For date selection
from bokeh.models import LassoSelectTool
from bokeh.models import Panel                      # For assigning grid to view
from bokeh.models.widgets import RadioButtonGroup   # Selecting layer

# For mapping
from bokeh.tile_providers import get_provider, Vendors
from bokeh.models import WMTSTileSource

# Custom layers
from world_grid_2_degree_layer import US_World_Grid_2_Degree_Layer
from us_county_layer import US_County_Layer
from us_state_layer import US_State_Layer

import shapely          # For checking shape type (Polygon/Multipolygon)
import numpy as np      # Converting lists to np lists (bugs out otherwise)

import pickle           # For saving layers
import os.path          # For checking if path exists
from os import path

# The date range the map should start on
START_DATE_INIT = date(2018, 9, 1)
END_DATE_INIT = date(2018, 9, 11)

# Initialize all layers

LAYERS_FILE = 'layers.dump'

# From a save file
if path.exists(LAYERS_FILE):
    with open(LAYERS_FILE, 'rb') as layers_file:
        us_county_layer, us_state_layer, world_grid_2_degree_layer \
                                        = pickle.load(layers_file)
# From scratch
else:
    us_county_layer = US_County_Layer()
    us_state_layer = US_State_Layer()
    world_grid_2_degree_layer = US_World_Grid_2_Degree_Layer()
    with open(LAYERS_FILE, 'wb') as layers_file:
        layers = (us_county_layer, us_state_layer, world_grid_2_degree_layer)
        pickle.dump(layers, layers_file)

# Set the active layer to be the county layer
active_layer = us_county_layer

# Function that generates the US visualization and passes the tab to main
def US_SIF_tab():

    #################################
    # Set up layer selector
    #################################

    # Once a new layer is selected, use that layer to refresh the page
    # and all data
    def refresh_page():
        
        # Obtain and update date boundaries
        start_date, end_date = active_layer.get_date_range()
        date_range_slider.start = start_date
        date_range_slider.end = end_date

        # Get initial map details
        xs, ys, names = active_layer.get_map_details()

        # print(xs)

        # Unpack the current range
        range_start, range_end = date_range_slider.value

        # Convert to SQL format
        range_start = utc_from_timestamp(range_start)
        range_end = utc_from_timestamp(range_end)

        # Get the initial sif values
        sifs = active_layer.get_data_for_date_range(range_start, 
                                                    range_end)

        # print(np.array(xs).tolist())

        # Dictionary to hold the data
        new_source_dict = dict(
            x= xs, y= ys,
            name= np.array(names), sifs= np.array(sifs))
        
        # Update all source data values
        source.data = new_source_dict

    # Trigger for when a new layer is selected
    def layer_selected(new):

        # We want to modify the global active layer (not local to this func)
        global active_layer

        # Simple dictionary to switch out the active layer
        switcher = {
            0 : None,
            1 : us_state_layer,
            2 : us_county_layer,
            3 : world_grid_2_degree_layer,
        }

        # Swap out the active layer
        active_layer = switcher.get(new, active_layer) 

        # TODO: If this is the custom layer, add the selection tool
            
        # Fetch new dates, shapes, names, etc. and refresh the page
        refresh_page()

    # Define selection labels
    layer_selector = RadioButtonGroup(
        labels=["Custom", "US States", "US Counties", "World"], active=2)

    # Set up layer selection callback
    layer_selector.on_click(layer_selected)

    #################################
    # Set up date range slider
    #################################

    # Obtain date boundaries
    start_date, end_date = active_layer.get_date_range()

    # create a callback for when the date slider is changed
    def date_range_selected(attr, old, new):

        t0 = time.time()

        # Unpack the new range
        range_start, range_end = new

        # Convert to SQL format
        range_start = utc_from_timestamp(range_start)
        range_end = utc_from_timestamp(range_end)
        
        # Get the new day's data
        sifs = active_layer.get_data_for_date_range(range_start, range_end)

        # Update the sif values
        source.data["sifs"] = np.array(sifs)

        # Set the title of the map to reflect the selected date
        p.title.text = "SIF Average by County: %s to %s" % (range_start, 
                                                            range_end)

        print("Took " + str(time.time() - t0) + " seconds to update")

    # Create the date slider
    date_range_slider = DateRangeSlider(title="Date Range: ", 
                                        start=start_date, end=end_date, 
                                        value=(START_DATE_INIT, 
                                            END_DATE_INIT), step=1)

    # Assign the callback for when the date slider changes
    date_range_slider.callback_policy = "throttle"
    date_range_slider.callback_throttle = 200
    date_range_slider.on_change('value_throttled', date_range_selected)

    #################################
    # Set up the map and its source
    #################################

    # Get initial map details
    xs, ys, names = active_layer.get_map_details()

    # Get the initial sif values 
    sifs = active_layer.get_data_for_date_range(START_DATE_INIT, 
                                                END_DATE_INIT)

    # Dictionary to hold the data
    source=ColumnDataSource(data = dict(
        x= np.array(xs),
        y= np.array(ys),
        name= np.array(names),
        sifs= np.array(sifs))
    )

    # Which tools should be available to the user
    TOOLS = "pan,wheel_zoom,reset,hover,save,tap"

    # Obtain map provider
    tile_provider = get_provider(Vendors.CARTODBPOSITRON_RETINA)

    # tile_options = {}
    # tile_options['url'] = 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}'
    # tile_options['attribution'] = """
    #     Map tiles by <a href="http://stamen.com">Stamen Design</a>, under
    #     <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>.
    #     Data by <a href="http://openstreetmap.org">OpenStreetMap</a>,
    #     under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.
    #     """
    # mq_tile_source = WMTSTileSource(**tile_options)

    # Don't want the map to wrap around
    tile_provider.wrap_around = False

    # Configure the figure
    p = figure(
        title="SIF Average by County: %s" % end_date, tools=TOOLS,
        active_scroll = "wheel_zoom",
        x_axis_location=None, y_axis_location=None,
        tooltips=[
            ("Name", "@name"), 
            ("Average SIF", "@sifs")
        ],
        x_axis_type='mercator',
        y_axis_type='mercator',
        plot_height = 900,
        plot_width = 1100,
        output_backend="webgl")

    # Add the map!
    p.add_tile(tile_provider)

    p.lod_threshold = None          # No downsampling
    p.toolbar.logo = None           # No logo
    p.grid.grid_line_color = None   # No grid

    # Policy for hovering
    p.hover.point_policy = "follow_mouse"

    # Color mapper
    color_mapper = LinearColorMapper(palette=palette, low = -1, high = 3)

    # Patch all the information onto the map
    p.patches('x', 'y', source=source,
              fill_color={'field': 'sifs', 'transform': color_mapper},
              fill_alpha=0.9, line_color="white", line_width=0.1, 
              legend = "Map")
    p.legend.location = "top_right"
    p.legend.click_policy="hide"
    p.title.text_font_size = '16pt'

    # Add a color bar
    ticker = FixedTicker(ticks=[-1,0,1,2])
    color_bar = ColorBar(color_mapper=color_mapper, ticker = ticker,
                     label_standoff=12, border_line_color=None, location=(0,0))
    p.add_layout(color_bar, 'right')

    #################################
    # Set up time series
    #################################

    def shape_selected(event):

        # Obtain selected geometry
        xs = np.array(list(event.geometry['x'].values()))
        ys = np.array(list(event.geometry['y'].values()))

        custom_data = dict(x= xs, y= ys)

        p.patch('x', 'y', source=custom_data,
              line_color="darkslategray", line_width=1, 
              fill_alpha=0.3, fill_color="lightgray",
              legend = "Selected Region")

        print("adding geometry")

        polygon_str = "POLYGON(("

        coords = list(zip(xs, ys))

        for x, y in coords:
            coord_x, coord_y = to_lat_lon(y, x)
            polygon_str += (str(coord_x) + " " + str(coord_y) + ",")

        x_first, y_first = coords[0]
        coord_x, coord_y = to_lat_lon(y_first, x_first)
        polygon_str += (str(coord_x) + " " + str(coord_y) + ",")

        polygon_str = polygon_str[:-1] + "))"

        cmd = " WITH area AS (SELECT ST_GeomFromText(\'%s\') AS shape)\
                SELECT date_trunc('day', time), \
                        AVG(sif) FROM tropomi_sif \
                WHERE ((SELECT shape FROM area) && center_pt) \
                        AND ST_CONTAINS((SELECT shape FROM area), center_pt)\
                GROUP BY date_trunc('day', time)\
                ORDER BY date_trunc('day', time);" % polygon_str

        # Obtain results
        result = query_db(cmd)

        # Check that there are sufficient values
        if len(result) <= 1:
            return 

        # Map the rows to columns and take series
        mapped_result = [list(i) for i in zip(*result)]
        dates, sifs = (mapped_result[0], mapped_result[1])

        # Set the appropriate data source
        time_srs_src.data = dict(date=dates, sif=sifs)
        

    def patch_clicked(event):

        # Obtain new information
        new_title, series_data = active_layer.get_patch_time_series(event)

        # Set the title of the Time Series plot
        sif_series.title.text = new_title

        # Set the appropriate data source
        time_srs_src.data = series_data

    # Source of the time-series data should be empty for now
    time_srs_src = ColumnDataSource(data=dict(date=[], sif=[]))

    # Which tools should be available to the user for the timer series
    TOOLS = "pan,wheel_zoom,reset,hover,save,tap"

    # Figure that holds the time-series
    sif_series = figure(plot_width=750, plot_height=400, x_axis_type='datetime',
                        tools=TOOLS, 
                        title= "SIF Time-Series (Select a county...)",
                        active_scroll = "wheel_zoom",
                        x_axis_label = 'Date',
                        y_axis_label = 'SIF Average')

    sif_series.scatter('date', 'sif', 
                        source=time_srs_src, color = 'green')

    # Some font choices
    sif_series.title.text_font_size = '16pt'
    sif_series.xaxis.axis_label_text_font_size = "12pt"
    sif_series.yaxis.axis_label_text_font_size = "12pt"

    # No logo
    sif_series.toolbar.logo = None

    # When a patch is selected, trigger the patch_time_series function
    p.on_event(Tap, patch_clicked)
    
    # On geometry selection
    lasso = LassoSelectTool(select_every_mousemove = False)
    p.add_tools(lasso)
    p.on_event(SelectionGeometry, shape_selected)

    #################################
    # Set up tab
    #################################

    # The layout of the view
    layout = row(column(p, date_range_slider, layer_selector), sif_series)

    # Create tab using layout
    tab = Panel(child=layout, title = 'US Visualization')

    # Return the created tab
    return tab