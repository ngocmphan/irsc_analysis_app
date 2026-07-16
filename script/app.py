# Import libraries
import streamlit as st
import pandas as pd
from pathlib import Path
import altair as alt

# Setting up Dashboard
st.set_page_config(
    page_title = "IRSC / CIHR Funding analytics Dashboard", 
    layout="wide"
)
PROV_COLORS = ['#2ca02c', '#9467bd', '#d62728', '#17becf', '#7f7f7f', '#bcbd22']
BAR_COLORS = ['#aec7e8', '#1f77b4']
NEUTRAL_BAR_COLOR = "#3d6292"

# Loading data
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_FILE = (SCRIPT_DIR.parent / "app_data" / "cihr_projects.parquet").resolve()
SUMMARY_FILE = (SCRIPT_DIR.parent / "app_data" / "cihr_summary_metrics.parquet").resolve()


# @st.cache_data
def load_data():
    """Load both parquet dataset"""
    # Initialize empty frames as fallbacks to ensure structural consistency
    df_p = pd.DataFrame()
    df_s = pd.DataFrame()
    
    try:
        if PROJECT_FILE.exists():
            df_p = pd.read_parquet(PROJECT_FILE)
        else:
            st.sidebar.warning(f"⚠️ {PROJECT_FILE.name} not found.")
            
        if SUMMARY_FILE.exists():
            df_s = pd.read_parquet(SUMMARY_FILE)
        else:
            st.sidebar.warning(f"⚠️ {SUMMARY_FILE.name} not found.")
            
    except Exception as e:
        st.sidebar.error(f"Error reading Parquet files: {e}")
        
    # CRITICAL: Always return a tuple of two items so unpacking never fails
    return df_p, df_s


df_projects, df_summary = load_data()

if df_summary.empty and df_projects.empty: 
    st.error("Data files not found. Please verify and run data_preprocess.py script")
    st.stop()

# -- HEADER SECTION --
st.title("IRSC / CIHR Funding results Dashboard")

# -- SIDEBAR FILTER --
st.sidebar.header("Dashboard Filters")

# Year filter
years = sorted(df_projects["competition_year"].unique().astype(int))
available_years = [x for x in years if x > 2021]
selected_year = st.sidebar.selectbox("Select fiscal year", options=available_years, index=len(available_years)-1)

# Filtered data
filtered_summary = df_summary[
    (df_summary['fiscal_year'] == selected_year)
]

filtered_results = df_projects[(df_projects["competition_year"] == selected_year)]

average_grant = filtered_results["cihr_contribution"].mean()/1000
median_grant = filtered_results["cihr_contribution"].median()/1000
total_amount = filtered_results["cihr_contribution"].sum()/1000000

if not filtered_summary.empty:
    filtered_summary["average_grant"] = average_grant
    filtered_summary["median_grant"] = median_grant
else: print("Error with calculation of mean and median grant")

# -- TABBED LAYOUT --
tab1, tab2, tab3 = st.tabs(["Provincial Summary Stats", "Detailed Project Explorer", "Information"])
#----------------------------------
#   TAB 1: PROVINCIAL COMPARISON
#----------------------------------

with tab1:
    st.subheader(f"Competition overview: {selected_year}")
    if filtered_summary.empty:
        st.warning("No summary data available for this specific year.")
    else:
        total_apps = int(filtered_summary["number_of_applications_submitted"].sum())
        total_funded = int(filtered_summary["number_of_applications_funded"].sum())
        national_success_rate = round((total_funded*100 / total_apps), 2)
        

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Total applications submitted", f"{total_apps:,}")
        col2.metric("Total Projects Funded", f"{total_funded:,}")
        col3.metric("National success rate", f"{national_success_rate}")
        col4.metric("Total funding amount", f"${total_amount:,.1f}M")
        col5.metric("Average grant amount", f"${average_grant:,.1f}K")
        col6.metric("Median grant amount", f"${median_grant:,.1f}K")

        st.markdown("### Provincial breakdown")

        # Display the main structured summary sheet cleanly with custom format settings
        st.dataframe(
            filtered_summary.drop(columns=['fiscal_year', 'occasion', 'source_file', "change_from_historical_applications", "change_from_historical_funded", "national_apps_submitted", "national_apps_funded", "average_grant", "median_grant", "total_median_weight_temp", "total_funding_temp", "median_grant_amount"], errors='ignore'),
            column_config={
                "province": st.column_config.TextColumn("Province"),
                "number_of_applications_submitted": st.column_config.NumberColumn("Apps Submitted", format="%d"),
                "percent_of_total_applications_submitted": st.column_config.NumberColumn("% of Total Apps", format="%.1f%%"),
                "number_of_applications_funded": st.column_config.NumberColumn("Apps Funded", format="%d"),
                "percent_of_applications_funded": st.column_config.NumberColumn("% of Total Funded", format="%.1f%%"),
                "provincial_success_rate": st.column_config.NumberColumn("Provincial Success Rate", format="%.1f%%"), 
                "average_grant_amount": st.column_config.NumberColumn("Average grant amount", format="$%,.2f")
                
            },
            hide_index=True,
            use_container_width=True
        )
        st.subheader("Application Volumes & Success Rate trends")

        # 1. Setup a multiselect tool in the main area (or sidebar) for comparing provinces
        all_provinces = sorted(df_summary['province'].unique())
        selected_provinces = st.multiselect(
            "Select Provinces to compare success rates against the National average:",
            options=all_provinces,
            default=[] # Starts with just the national average displayed
        )
        
        # 2. Prepare National Dataset (Aggregated from all summary rows per year)
        national_trends = df_summary.groupby('fiscal_year').agg(
            total_submitted=('number_of_applications_submitted', 'sum'),
            total_funded=('number_of_applications_funded', 'sum')
        ).reset_index()

        national_trends['National Success Rate'] = (
            (national_trends['total_funded'] / national_trends['total_submitted']) * 100
        ).round(1)

        # 3. Create the Base Layer: Total Apps Submitted (Full Width, Light Color)
        submitted_bars = alt.Chart(national_trends).mark_bar(
            color='#aec7e8', 
            opacity=0.6,
            size=40 # Controls bar thickness
        ).encode(
            x=alt.X('fiscal_year:O', title='Fiscal Year'),
            y=alt.Y('total_submitted:Q', title='Number of Applications'),
            tooltip=[
                alt.Tooltip('fiscal_year', title='Year'),
                alt.Tooltip('total_submitted', title='Total Submitted')
            ]
        )

        # 4. Create the Overlay Layer: Apps Funded (Narrower Width, Darker Color)
        funded_bars = alt.Chart(national_trends).mark_bar(
            color='#1f77b4',
            size=24 # Slightly narrower so it sits inside the submitted bar cleanly
        ).encode(
            x='fiscal_year:O',
            y='total_funded:Q',
            tooltip=[
                alt.Tooltip('fiscal_year', title='Year'),
                alt.Tooltip('total_funded', title='Total Funded'),
                alt.Tooltip('National Success Rate', title='National Success Rate (%)')
            ]
        )

        # Combine the volume bars together as a single layered asset
        volume_chart = alt.layer(submitted_bars, funded_bars)

        # 5. Create the National Success Rate Line (Right Axis - Dashed)
        line_charts = alt.Chart(national_trends).mark_line(
            strokeDash=[5, 5], color='#1f77b4', strokeWidth=3, point=True
        ).encode(
            x='fiscal_year:O',
            y=alt.Y('National Success Rate:Q', title='Success Rate (%)', scale=alt.Scale(domain=[0, 100])),
            tooltip=['fiscal_year', 'National Success Rate']
        )

        # 6. Dynamically add solid trend lines for selected comparison provinces
        if selected_provinces:
            prov_df = df_summary[df_summary['province'].isin(selected_provinces)].copy()
            
            prov_line_chart = alt.Chart(prov_df).mark_line(point=True, strokeWidth=2).encode(
                x='fiscal_year:O',
                y='provincial_success_rate:Q',
                color=alt.Color(
            'province:N', 
            title='Rates By Province',
            scale=alt.Scale(range=PROV_COLORS) 
            ),
                tooltip=['fiscal_year', 'province', 'provincial_success_rate']
            )
            line_charts = alt.layer(line_charts, prov_line_chart)

        # 7. Bind everything together using Dual-Axis isolation
        final_combined_chart = alt.layer(
            volume_chart, 
            line_charts
        ).resolve_scale(
            y='independent' # Separates raw counts on the left from percentages on the right
        ).properties(
            width=700,
            height=450
        )

        st.altair_chart(final_combined_chart, use_container_width=True)



#----------------------------------
#   TAB 2: DETAILED EXPLORATION
#----------------------------------

with tab2:
    
    if df_projects.empty:
        st.info("Detailed project information sheet is not loaded or available.")
    else:
        
            # --- 1. INITIALIZE SELECTED STATE ---
        if "selected_analysis_view" not in st.session_state:
            st.session_state.selected_analysis_view = "Research Category"  # Default view

        # --- 2. DEFINE THE FUNDING DASHBOARD CARDS ---
        analysis_cards = [
            {
                "id": "Research Category", 
                "label": "Research Category", 
                "preview": "📊", 
                "desc": "Funding by fields"
            },
            {
                "id": "Top 10 Institutions", 
                "label": "Top 10 Institutions", 
                "preview": "🏆", 
                "desc": "Leading recipients"
            },
            {
                "id": "Institution Comparison", 
                "label": "Institution Comparison", 
                "preview": "🔄", 
                "desc": "Side-by-side metrics"
            }
        ]

        # --- 3. RENDER THE CARD ROW ---
        # Create 4 columns matching the 4 visual cards
        card_cols = st.columns(3)

        for i, card in enumerate(analysis_cards):
            with card_cols[i]:
                # Track active card selection
                is_selected = st.session_state.selected_analysis_view == card["id"]
                
                # Interactive styling based on focus/active state
                if is_selected:
                    border_style = "border: 2px solid #ff4b4b; background-color: #fff8f8; box-shadow: 0px 4px 12px rgba(255, 75, 75, 0.15);"
                    text_color = "#ff4b4b"
                    desc_color = "#ff4b4b"
                else:
                    border_style = "border: 1px solid #e0e0e0; background-color: #ffffff;"
                    text_color = "#333333"
                    desc_color = "#888888"

                # Clean card visual frame (mimics your exact screenshot layout)
                st.markdown(f"""
                    <div style="
                        text-align: center; 
                        padding: 15px 5px; 
                        border-radius: 8px; 
                        height: 150px;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        transition: 0.2s;
                        {border_style}
                    ">
                        <div>
                            <div style="font-weight: bold; font-size: 14px; color: {text_color}; line-height: 1.2;">{card['label']}</div>
                            <div style="font-size: 11px; color: {desc_color}; margin-top: 3px;">{card['desc']}</div>
                        </div>
                        <div style="font-size: 32px; line-height: 1; margin-bottom: 5px;">{card['preview']}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # The click trigger directly beneath the card layout
                if st.button(
                    f"Open {card['label']}", 
                    key=f"btn_nav_{card['id']}", 
                    use_container_width=True,
                    type="primary" if is_selected else "secondary"
                ):
                    st.session_state.selected_analysis_view = card["id"]
                    st.rerun()

        st.markdown("---")
        # =========================================================================
        # SUB-TAB 1: RESEARCH CATEGORY
        # =========================================================================
        # Filter down the massive projects dataset by selected year to keep response snappier
        year_projects = df_projects[df_projects['competition_year'] == selected_year]
        average_funding = year_projects["cihr_contribution"].mean()
        if st.session_state.selected_analysis_view == "Research Category":
            st.subheader(f"Research Category Distribution: {selected_year}" )
            st.markdown("Analyze how funding and project volumes are distributed across different fields.")

            # Grouping by PRC Category
            prc_stats = year_projects.groupby('prc_category').agg(
                total_funding=('cihr_contribution', 'sum'),
                average_funding=('cihr_contribution', 'mean'),
                project_count=('cihr_contribution', 'count')
            ).reset_index()

            top_5_total = prc_stats.nlargest(5, 'total_funding')
            top_5_avg = prc_stats.nlargest(5, 'average_funding')
            top_category_name = top_5_total.iloc[0]['prc_category']
            top_category_value = top_5_total.iloc[0]['total_funding']
            top_avg_name = top_5_avg.iloc[0]["prc_category"]
            top_avg_value = top_5_avg.iloc[0]["average_funding"]

            st.markdown(f"In {selected_year}, {top_category_name} received the highest total funding at \\${top_category_value:,.0f}, and {top_avg_name} topped the list for highest average funding at \\${top_avg_value:,.0f} per project.")
            st.markdown(f"In general, the average funding per project for {selected_year} is \\${average_funding: ,.0f}.")
            ## -- SECTION 1: TOP 5 PRC CATEGORIES
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Total Funding by research category")
                chart_prc_total = alt.Chart(top_5_total).mark_bar(color=NEUTRAL_BAR_COLOR).encode(
                    x=alt.X('total_funding:Q', title='Total Funding ($)'),
                    y=alt.Y('prc_category:N', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
                    tooltip=[alt.Tooltip('prc_category', title='PRC'), alt.Tooltip('total_funding', title='Total Funding', format='$,.0f'), alt.Tooltip('project_count:Q', title='Total Projects', format=',.0f')]
                ).properties(height=250)
                st.altair_chart(chart_prc_total, width="stretch")

            with col2:
                st.markdown("#### Average Funding per Project by research category")
                chart_prc_avg = alt.Chart(top_5_avg).mark_bar(color=NEUTRAL_BAR_COLOR).encode(
                    x=alt.X('average_funding:Q', title='Average Funding ($)'),
                    y=alt.Y('prc_category:N', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
                    tooltip=[alt.Tooltip('prc_category', title='PRC'), alt.Tooltip('average_funding', title='Average Funding', format='$,.0f'), alt.Tooltip('project_count:Q', title='Total Projects', format=',.0f')]
                ).properties(height=250)
                st.altair_chart(chart_prc_avg, width="stretch")

        # =========================================================================
        # SUB-TAB 2: TOP 10 INSTITUTIONS
        # =========================================================================
        elif st.session_state.selected_analysis_view == "Top 10 Institutions":
            st.subheader(f"Top 10 institutions: {selected_year}")
            st.markdown("Overview of the leading institutions by total funding allocations.")
            ## -- SECTION 2: TOP 10 INSTITUTIONS
            inst_stats = year_projects.groupby('institution').agg(
                number_of_projects=('cihr_contribution', 'count'),
                total_funding=('cihr_contribution', 'sum'),
                average_funding=('cihr_contribution', 'mean')
            ).reset_index()

            # Isolate the top 10 assets for each metric separately
            top_10_total_funding = inst_stats.nlargest(10, 'total_funding')
            top_10_avg_funding = inst_stats.nlargest(10, 'average_funding')
            top_10_total_projects = inst_stats.nlargest(10, 'number_of_projects')
            previous_year = selected_year - 1

            # Filter raw data for last year
            prev_year_projects = df_projects[df_projects['competition_year'] == previous_year]

            # Calculate stats for last year
            prev_inst_stats = prev_year_projects.groupby('institution').agg(
                number_of_projects=('cihr_contribution', 'count'),
                total_funding=('cihr_contribution', 'sum'),
                average_funding=('cihr_contribution', 'mean')
            ).reset_index()

            # 4. Extract Top 3 for both years
            current_top_3_total = top_10_total_funding.head(3)
            current_top_3_avg = top_10_avg_funding.head(3)

            prev_top_3_total = prev_inst_stats.nlargest(3, 'total_funding')
            prev_top_3_avg = prev_inst_stats.nlargest(3, 'average_funding')

            # Total funding comparison logic
            curr_total_set = set(current_top_3_total['institution'])
            prev_total_set = set(prev_top_3_total['institution'])
            new_total_additions = curr_total_set - prev_total_set
            curr_total_str = ", ".join(current_top_3_total['institution'])

            if len(new_total_additions) == 0:
                # Scenario A: No changes at all (same cohort)
                curr_sum = current_top_3_total['total_funding'].sum()
                prev_sum = prev_top_3_total['total_funding'].sum()
                pct_change = ((curr_sum - prev_sum) / prev_sum) * 100
                
                total_comparison_text = (
                    f"The top 3 institutions remained the same as in {previous_year} "
                    f"({curr_total_str}), with their combined total funding changing by "
                    f"**{pct_change:+.1f}%** (totaling **\\${curr_sum:,.0f}**)."
                )

            elif len(new_total_additions) == 3:
                # Scenario B: Complete turnover (all 3 are brand new)
                total_comparison_text = (
                    f"A completely new lineup has claimed the top 3 spots this year: **{curr_total_str}**."
                )

            else:
                # Scenario C: Partial turnover (1 or 2 new additions)
                new_list_str = ", ".join(new_total_additions)
                total_comparison_text = (
                    f"The top 3 lineup has shifted. Current leaders are **{curr_total_str}**, "
                    f"with **{new_list_str}** joining the leading tier."
                )
            
            # Average funding comparison logic
            curr_avg_set = set(current_top_3_avg['institution'])
            prev_avg_set = set(prev_top_3_avg['institution'])
            new_avg_additions = curr_avg_set - prev_avg_set
            curr_avg_str = ", ".join(current_top_3_avg['institution'])

            if len(new_avg_additions) == 0:
                # Scenario A: No changes at all (same cohort)
                curr_avg_mean = current_top_3_avg['average_funding'].mean()
                prev_avg_mean = prev_top_3_avg['average_funding'].mean()
                pct_change_avg = ((curr_avg_mean - prev_avg_mean) / prev_avg_mean) * 100
                
                avg_comparison_text = (
                    f"The top 3 institutions by average grant size remained the same "
                    f"({curr_avg_str}), with a combined average shifting by "
                    f"**{pct_change_avg:+.1f}%** (averaging **\\${curr_avg_mean:,.0f}** per project)."
                )

            elif len(new_avg_additions) == 3:
                # Scenario B: Complete turnover (all 3 are brand new)
                avg_comparison_text = (
                    f"A completely new set of institutions now leads in average grant size: **{curr_avg_str}**."
                )

            else:
                # Scenario C: Partial turnover (1 or 2 new additions)
                new_avg_str = ", ".join(new_avg_additions)
                avg_comparison_text = (
                    f"The top 3 high-intensity lineup changed since last year. Current leaders are **{curr_avg_str}**, "
                    f"with **{new_avg_str}** climbing into the top spots."
                )

            # Summary analysis
            st.markdown(f"""
            * **Total Funding:** {total_comparison_text}
            * **Average Grant Size:** {avg_comparison_text}
            """)
            # Split layout into side-by-side slots
            inst_col1, inst_col2 = st.columns(2)
            
            with inst_col1:
                st.markdown("#### Top 10: Most Total Funding")
                chart_inst_total = alt.Chart(top_10_total_funding).mark_bar(color=NEUTRAL_BAR_COLOR).encode(
                    x=alt.X('total_funding:Q', title='Total Combined Allocations ($)'),
                    y=alt.Y('institution:N', sort='-x', title=None, axis=alt.Axis(labelLimit=350)),
                    tooltip=[
                        alt.Tooltip('institution', title='Institution'), 
                        alt.Tooltip('total_funding', title='Total Funding', format='$,.0f'),
                        alt.Tooltip('number_of_projects', title='Total Projects')
                    ]
                ).properties(height=350)
                
                st.altair_chart(chart_inst_total, width="stretch")

            with inst_col2:
                st.markdown("#### Top 10: Highest Average Funding")
                chart_inst_avg = alt.Chart(top_10_avg_funding).mark_bar(color=NEUTRAL_BAR_COLOR).encode(
                    x=alt.X('average_funding:Q', title='Average Grant Value ($)'),
                    y=alt.Y('institution:N', sort='-x', title=None, axis=alt.Axis(labelLimit=350)),
                    tooltip=[
                        alt.Tooltip('institution', title='Institution'), 
                        alt.Tooltip('average_funding', title='Average Value', format='$,.0f'),
                        alt.Tooltip('number_of_projects', title='Total Projects')
                    ]
                ).properties(height=350)
                
                st.altair_chart(chart_inst_avg, width="stretch")


        # =========================================================================
        # SUB-TAB 3: INSTITUTION COMPARISON
        # =========================================================================
        elif st.session_state.selected_analysis_view == "Institution Comparison":
            st.subheader("Institutional Comparative Analysis")
            st.markdown("Directly compare performance metrics across selected institutions.")
            all_institutions = sorted(df_projects['institution'].unique())
            selected_inst = st.multiselect(
                "Select one or more institutions to compare the historical IRSC funding performance, up to 4 institutions:", 
                options=all_institutions, max_selections= 4, 
                default="Centre hospitalier de l'Université de Montréal (CHUM)"
            )

            if selected_inst:
                df_filtered_trend = df_projects[df_projects["institution"].isin(selected_inst)]

                # Yearly metrics aggregation:
                yearly_stats = df_filtered_trend.groupby(["competition_year", "institution"]).agg(
                    number_projects = ("cihr_contribution", "count"),
                    total_funding = ("cihr_contribution", "sum"), 
                    average_funding = ("cihr_contribution", "mean")
                ).reset_index()
                

                col1, col2, col3 = st.columns(3)
                with col1:
                    total_project_chart = alt.Chart(yearly_stats).mark_line(point=True, strokeWidth=3).encode(
                        x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                        y=alt.Y('number_projects:Q', title='Total number of projects funded'),
                        color=alt.Color('institution:N', 
                                title='Selected Institutions', 
                                legend=alt.Legend(orient='top', direction='vertical', labelLimit=350, labelFontSize=15)),
                        tooltip=['competition_year', 'institution', alt.Tooltip('number_projects', format=',.0f')]
                    ).properties(title="Total Projects Funded",height=350, width= "container")
                    st.altair_chart(total_project_chart, width="stretch")
                
                with col2:
                    total_trend_chart = alt.Chart(yearly_stats).mark_line(point=True, strokeWidth=3).encode(
                        x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                        y=alt.Y('total_funding:Q', title='Total Capitalized Pool ($)'),
                        color=alt.Color('institution:N', legend=None),
                        tooltip=['competition_year', 'institution', alt.Tooltip('total_funding', format='$,.0f')]
                    ).properties(title="Total Funding per year", 
                        height=350, width= "container")
                    st.altair_chart(total_trend_chart.configure_legend(disable=True), width="stretch")

                with col3: 
                    avg_trend_chart = alt.Chart(yearly_stats).mark_line(point=True, strokeWidth=3).encode(
                        x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                        y=alt.Y('average_funding:Q', title='Mean Funding Amount ($)'),
                        color=alt.Color('institution:N', legend=None),
                        tooltip=['competition_year', 'institution', alt.Tooltip('average_funding', format='$,.0f')]
                    ).properties(title="Average Funding per Grant per year",
                        height=350, width = "container")
                    st.altair_chart(avg_trend_chart.configure_legend(disable=True), width="stretch")
                
                ## -- SECTION 4: ANNUAL % CHANGE --
                yearly_stats = yearly_stats.sort_values(["institution", "competition_year"])
                yearly_stats['proj_pct_change'] = yearly_stats.groupby('institution')['number_projects'].pct_change() * 100
                yearly_stats['funding_pct_change'] = yearly_stats.groupby('institution')['total_funding'].pct_change() * 100
                yearly_stats['avg_pct_change'] = yearly_stats.groupby('institution')['average_funding'].pct_change() * 100
                yearly_stats_pct = yearly_stats

                pct_col1, pct_col2, pct_col3 = st.columns(3)
                proj_pct_chart = alt.Chart(yearly_stats_pct).mark_line(point=True, strokeWidth=3).encode(
                    x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                    y=alt.Y('proj_pct_change:Q', title='Project Volume Change (%)', axis=alt.Axis(format='+,.1f', titlePadding=20)),
                    color=alt.Color('institution:N', legend=None),
                    tooltip=['competition_year', 'institution', alt.Tooltip('proj_pct_change', format='+,.2f', title='Project Change %')]
                ).properties(title="Project Volume Growth (YoY %)", height=300, width='container')

                fund_pct_chart = alt.Chart(yearly_stats_pct).mark_line(point=True, strokeWidth=3).encode(
                    x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                    y=alt.Y('funding_pct_change:Q', title='Total Funding Change (%)', axis=alt.Axis(format='+,.1f', titlePadding=20)),
                    color=alt.Color('institution:N', legend=None),
                    tooltip=['competition_year', 'institution', alt.Tooltip('funding_pct_change', format='+,.2f', title='Total Funding Change %')]
                ).properties(title="Total Funding Growth (YoY %)", height=300, width='container')

                avg_pct_chart = alt.Chart(yearly_stats_pct).mark_line(point=True, strokeWidth=3).encode(
                    x=alt.X('competition_year:O', title='Fiscal Competition Year'),
                    y=alt.Y('avg_pct_change:Q', title='Mean Grant Change (%)', axis=alt.Axis(format='+,.1f', titlePadding=20)),
                    color=alt.Color('institution:N', legend=None),
                    tooltip=['competition_year', 'institution', alt.Tooltip('avg_pct_change', format='+,.2f', title='Avg Grant Change %')]
                ).properties(title="Average Amount per Grant Growth (YoY %)", height=300, width='container')

                zero_rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#555555',       # Darker charcoal gray for high contrast
                strokeWidth=2.0,       # Thicker stroke so it's clearly visible behind lines
                strokeDash=[0]         # Solid line (use [4, 4] if you prefer a heavy dash instead)
                ).encode(
                    y='y:Q'
                )
                # --- 3. RENDER THE LAYERED CHARTS OVER THE 0% MARKS ---
                with pct_col1:
                    st.altair_chart(alt.layer(zero_rule, proj_pct_chart), width="stretch")
                    
                with pct_col2:
                    st.altair_chart(alt.layer(zero_rule, fund_pct_chart), width="stretch")
                    
                with pct_col3:
                    st.altair_chart(alt.layer(zero_rule, avg_pct_chart), width="stretch")
            
            else:
                st.info("Please select at least one institution from the dropdown list to generate the comparison charts.")


with tab3:
    st.title("About This Dashboard")
    st.markdown(
        "This dashboard serves as an interactive tool to analyze and explore health research funding trajectories. "
        "To ensure transparency in how these metrics are calculated, please review the data sources, update schedules, "
        "and analytical limitations detailed below."
    )
    st.markdown("Contact: Alicia Ngoc Phan")
    st.markdown("---")

    # =========================================================================
    # DATA SOURCES SECTION
    # =========================================================================
    st.header("Data Sources")
    st.markdown(
        "The dashboard aggregates data from **two distinct sources** to balance high-level "
        "provincial comparisons with granular project-level exploration:"
    )

    # We use columns to present the two sources side-by-side cleanly
    col_src1, col_src2 = st.columns(2)
    
    with col_src1:
        st.subheader("1. Provincial Summaries")
        st.markdown(
            "**Source:** [CIHR Provincial Funding Summaries](https://cihr-irsc.gc.ca/e/51315.html)\n\n"
            "**Scope:** Provides official provincial-level funding allocations and comparison metrics "
            "aggregated by competition."
        )
        
    with col_src2:
        st.subheader("2. Project-Level Decisions")
        st.markdown(
            "**Source:** Extracted directly from the official **CIHR Funding Decisions Database**.\n\n"
            "**Scope:** Provides highly detailed institutional, researcher, and program-level data."
        )

    # Highlights the structural difference regarding catalyst projects
    st.warning(
        "**Note on Catalyst Projects:** "
        "The official *Provincial Summaries* source **does not** include Catalyst Projects in its totals. "
        "However, the *Funding Decisions Database* extracts **do** include these projects as part of the "
        "broader Project Grant Program. To reconcile this, this dashboard counts Catalyst Projects "
        "**exclusively within the Detailed Project Explorer analysis** tabs."
    )

    st.markdown("---")

    # =========================================================================
    # FREQUENCY OF UPDATES & LIMITATIONS
    # =========================================================================
    col_meta1, col_meta2 = st.columns(2)

    with col_meta1:
        st.header("Frequency of Updates")
        st.markdown(
            "* **Schedule:** Updated **twice per year**.\n"
            "* **Timing:** Data refreshes are processed dynamically as soon as official data releases "
            "become available following the conclusion of each major competition cycle."
        )

    with col_meta2:
        st.header("Analytical Limitations")
        st.markdown(
            "* **Provincial Classifications:** The *Funding Decisions Database* contains detailed "
            "institutional profiles but lacks provincial classification tags.\n"
            "* **Tab Separation:** Because institutional data cannot be cleanly mapped back to "
            "provincial-level summaries without risking discrepancies, the **Provincial Summary Stats** "
            "tab relies entirely on the first data source (*Provincial Summaries*). \n"
            "* **Average grant amount (Weighted) by province**: "
            "Because the detailed institutional database lacks provincial classifications, provincial metrics "
            "are computed using the aggregated *Provincial Summaries*.\n\n"
            "Since each calendar year comprises two separate competition cycles (Spring and Fall) with varying "
            "project volumes, a simple average of the two cycles would bias the yearly results. "
            "Instead, the yearly provincial average is calculated as a **weighted average**:\n\n"
            "$$\\text{Weighted Average} = \\frac{(\\text{Avg}_{\\text{Spring}} \\times N_{\\text{Spring}}) + (\\text{Avg}_{\\text{Fall}} \\times N_{\\text{Fall}})}{N_{\\text{Spring}} + N_{\\text{Fall}}}$$\n\n"
            "This ensures that competition cycles with higher project volumes are weighted proportionally "
            "when looking at full-year provincial performance."
        )

