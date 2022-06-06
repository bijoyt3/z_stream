import streamlit as st
import sqlite3
import pandas as pd
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder
from pyecharts import options as opts
from pyecharts.charts import Bar
from streamlit_echarts import st_pyecharts
import plotly.express as px
import numpy as np

# Connect to sqlite database
conn = sqlite3.connect('listings_v4.db')

# Master/Cleaned df
all_ = pd.read_sql("select * from listings_v4", conn)
all_.drop('Zipcode', axis=1, inplace=True)
all_['Zipcode'] = all_['Address'].apply(lambda x: x[-5:])
all_ = all_[~pd.to_numeric(all_['Zipcode'], errors='coerce').isnull()]
all_.dropna(inplace=True)
all_['Square Footage'] = all_['Square Footage'].astype(int)
all_['Bedrooms'] = all_['Bedrooms'].astype(int)
all_['ZDelta'] = all_['ZDelta'].astype(int)
all_.drop_duplicates(subset='zpid', keep='last', inplace=True)
all_.sort_values(by='ZDelta', ascending=False, inplace=True)
all_.reset_index(drop=True, inplace=True)

# Streamlit starts here
st.set_page_config(layout='wide')
st.info("Dataset Last Updated: {}".format(all_['LastUpdated'].head(1)[0]))
st.title("🏠 Zillow Zestimate Analysis 🏠")
st.caption("Brought to you by BJT Studios")

# Sidebar text
with st.sidebar:
    st.write("""
    ## About:
    
    Welcome to the **🏠 Zillow Zestimate Analysis Tool 🏠️**. The intent of this application is to visualize the housing
    market landscape in Loudoun County and Fairfax County. It also should provide insight into the delta between
    a property's list price and its Zestimate value to allow prospective homebuyers to browse "undervalued" 
    properties. 
    
    A [Zestimate](https://www.zillow.com/z/zestimate/#:~:text=The%20Zestimate%C2%AE%20home%20valuation,in%20place%20of%20an%20appraisal)
    is Zillow's estimate of a property's market value calculated by a proprietary algorithm. This is different from a 
    home's listed sales price. Scroll down to the section titled "How is the Zestimate calculated?" in the above link
    to gain insight around their valuation methdology.
    
    ## Data:
    
    The dataset presented only includes **homes for sale** within **Loudoun County and Fairfax County zipcodes that have 
    a Zestimate**. Some homes for sale do not have a Zestimate for whatever reason. These homes were removed from the
    dataset. 
    
    ## Zestimate Accuracy:
    
    There is much speculation on the accuracy of a home's Zestimate - in the above link, Zillow graciously offers a 
    table of accuracy statistics of active listings by metro area, state, and nationally. They also offer an Excel 
    export that includes a breakdown by county. 
    
    _As of June 1st, 2022:_ 
    
    Loudoun County has a 1% median error rate with 96.7% of listings being within 5% of the sales price for on-market
    homes.
    
    Fairfax County has a 1.1% median error rate with 95.2% of listings being within 5% of the sales price for on-market
    homes.
    """)

# Listings with >=10% positive ZDelta
undervalued = all_.where(all_['ZDelta']/all_['ListedPrice'] >= .1).dropna()

# Metrics Container
st.write("#### Metrics")
with st.container() as metrics:
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric(label='# of Listings', value=len(all_))

    with m_col2:
        st.metric(label='# of Undervalued Listings (>=10% ZDelta)', value=len(undervalued))

    with m_col3:
        st.metric(label='Highest ZDelta', value="${}".format(all_['ZDelta'].head(1)[0]))

# Num. of Listings by Home Type
counts = all_.groupby('HomeType')['HomeType'].count().reset_index(name='count').sort_values(by='count', ascending=False)

# Avg. Price of Listing by Home Type
avg_price = all_.groupby('HomeType')['ListedPrice'].mean().reset_index(name='avg').sort_values(by='avg', ascending=False)
avg_price['avg'] = avg_price['avg'].div(1000).astype('int64')

# Barcharts Container
with st.container() as barcharts:
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        count_bar = (
            Bar(
                init_opts=opts.InitOpts()
            )
            .add_xaxis(counts['HomeType'].tolist())
            .add_yaxis("Number of Listings", counts['count'].tolist(), color='#011f4b')
            .set_global_opts(title_opts=opts.TitleOpts(title='Count of Listings by Home Type'),
                             toolbox_opts=opts.ToolboxOpts(is_show=False), legend_opts=opts.LegendOpts(pos_right=True))
        )

        st_pyecharts(count_bar, key="countBar")

    with b_col2:
        avg_bar = (
            Bar()
            .add_xaxis(avg_price['HomeType'].tolist())
            .add_yaxis("Average Price", avg_price['avg'].tolist(),
                       label_opts=opts.LabelOpts(formatter="${c}k"))
            .set_global_opts(title_opts=opts.TitleOpts(title='Average List Price by Home Type',
                                                       subtitle='Values in $000s'),
                             toolbox_opts=opts.ToolboxOpts(is_show=False), legend_opts=opts.LegendOpts(pos_right=True),
                             tooltip_opts=opts.TooltipOpts(formatter="${c}k"))
        )

        st_pyecharts(avg_bar, key="averageBar")

# Create scatter_mapbox dataframe
scatter_df = all_[['latitude', 'longitude', 'ZDelta', 'Address', 'ListedPrice', 'Zestimate', 'HomeType']].copy()

# Set labels for ZDelta from 1 to 5. 1 = negative, 2 through 5 is an even split between the number of records >= 0
gtz = scatter_df[scatter_df['ZDelta'] >= 0]
bins = 4
z3, z2, z1 = [gtz['ZDelta'].iloc[i * (len(gtz) // bins)] for i in range(1, bins)]

conditions = [
    (scatter_df['ZDelta'] < 0),
    (scatter_df['ZDelta'] >= 0) & (scatter_df['ZDelta'] <= z1),
    (scatter_df['ZDelta'] > z1) & (scatter_df['ZDelta'] <= z2),
    (scatter_df['ZDelta'] > z2) & (scatter_df['ZDelta'] <= z3),
    (scatter_df['ZDelta'] > z3)]

values = [1, 2, 3, 4, 5]
scatter_df['zd_score'] = np.select(conditions, values)

# Scatter Mapbox Container
st.info("")
st.write("#### Listing Locations")
st.caption("All listings visualized and sized by their ZDelta; the higher the ZDelta Score,"
           " the more 'undervalued' a listing is")
with st.container() as scattermap:
    fig = px.scatter_mapbox(scatter_df,
                            lat="latitude", lon="longitude", color="zd_score", size="zd_score",
                            color_continuous_scale='rdylgn', size_max=10, zoom=9,
                            center={'lat': 39, 'lon': -77.5}, height=750, hover_name='Address',
                            hover_data={
                                'zd_score': False,
                                'latitude': False,
                                'longitude': False,
                                'ListedPrice': ':,',
                                'Zestimate': ':,',
                                'ZDelta': ':,',
                                'HomeType': True
                            })

    fig.update_traces(hovertemplate='<b>%{hovertext}</b><br>'
                                    '<br>ListedPrice: $%{customdata[3]:,}'
                                    '<br>Zestimate: $%{customdata[4]:,}'
                                    '<br>ZDelta: $%{customdata[5]:,}'
                                    '<br>HomeType: %{customdata[6]}')

    fig.update_layout(mapbox_style="carto-positron",
                      hoverlabel=dict(
                          font_size=12,
                          font_family="Arial"
                      ))

    st.plotly_chart(fig, use_container_width=True)

# Search Listings Form
st.info("")
st.write("#### Search Listings")
with st.form(key='searchListings') as search:
    hometypes = st.multiselect(label="Select a HomeType:", options=scatter_df.HomeType.unique(),
                               default=scatter_df.HomeType.unique(),
                               help='Choose 1 or many options!')

    sizes = st.multiselect(label="Select a ZDelta Score:", options=scatter_df['zd_score'].unique(),
                               default=scatter_df['zd_score'].unique(),
                               help='Choose 1 or many options!')
    st.caption("_ZDelta Score_ is labeled from 1 to 5, with 1 being the lowest and 5 being the highest")

    submitted = st.form_submit_button("Search!")
    fig2 = px.scatter_mapbox(scatter_df[scatter_df['HomeType'].isin(hometypes) & scatter_df['zd_score'].isin(sizes)],
                             lat="latitude", lon="longitude", zoom=9, mapbox_style="carto-positron",
                             center={'lat': 39, 'lon': -77.5}, height=750, hover_name='Address',
                             hover_data={
                                'zd_score': False,
                                'latitude': False,
                                'longitude': False,
                                'ListedPrice': ':,',
                                'Zestimate': ':,',
                                'ZDelta': ':,',
                                'HomeType': True
                            })

    fig2.update_traces(hovertemplate='<b>%{hovertext}</b><br>'
                                    '<br>ListedPrice: $%{customdata[3]:,}'
                                    '<br>Zestimate: $%{customdata[4]:,}'
                                    '<br>ZDelta: $%{customdata[5]:,}'
                                    '<br>HomeType: %{customdata[6]}',
                       marker=dict(size=12, color='#097969'))

    fig2.update_layout(hoverlabel=dict(
                          font_size=12,
                          font_family="Arial"))

    if submitted:
        st.success("Returned {} Listings".format(len(fig2['data'][0]['customdata'])))
        st.plotly_chart(fig2, use_container_width=True)

# Display dataframes as AgGrid
with st.container() as dataframes:
    with st.expander("All Listings"):
        gob = GridOptionsBuilder.from_dataframe(all_)
        gob.configure_side_bar()
        AgGrid(all_, gridOptions=gob.build(), enable_enterprise_modules=True, theme='streamlit')
        st.caption("Number of Records: {}".format(len(all_)))

    with st.expander("Undervalued Listings"):
        st.caption("_Undervalued Listings_ are defined as listings with a >= 10% delta in Zestimate and list price")
        gob = GridOptionsBuilder.from_dataframe(undervalued)
        gob.configure_side_bar()
        AgGrid(undervalued, gridOptions=gob.build(), enable_enterprise_modules=True, theme='streamlit')
        st.caption("Number of Records: {}".format(len(undervalued)))


# Balloons on click for download button
def success():
    st.balloons()


@st.cache
def convert_df(df: pd.DataFrame):
    return df.to_csv().encode('utf-8')


all_listings = convert_df(all_)
uv_listings = convert_df(undervalued)

# Export dataframes as csv with download buttons
with st.container() as download_buttons:
    l1_dcol1, l1_dcol2, l1_dcol3 = st.columns([3, 1, 3])

    with l1_dcol2:
        l1_dcol2 = st.download_button(label='Download All Listings',
                                      data=all_listings,
                                      file_name='all_listings.csv',
                                      mime='text/csv',
                                      on_click=success)

    l2_dcol1, l2_dcol2, l2_dcol3 = st.columns([3, 1.5, 3])
    with l2_dcol2:
        l2_dcol2 = st.download_button(label='Download Undervalued Listings',
                                      data=uv_listings,
                                      file_name='uv_listings.csv',
                                      mime='text/csv',
                                      on_click=success)
st.info("")
