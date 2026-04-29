from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from shiny import reactive, req
from shiny.express import input, render, ui
from shinywidgets import render_plotly
from coords import MUNI_COORDS


def load_data(path: str | Path | None = None) -> pd.DataFrame:
    """Load data.json into a flat DataFrame.

    Top-level scalar fields become columns directly.
    Nested Property Classes are flattened to columns like:
        'Residential Tax Rate', 'Residential Taxable Value', 'Residential Tax Multiple', ...
    """
    if path is None:
        here = Path(__file__).parent
        path = here / "data.json" if (here / "data.json").exists() else Path("data.json")

    with open(path) as f:
        records = json.load(f)

    df = pd.json_normalize(records, sep=" ")
    df.columns = [col.removeprefix("Property Classes ") for col in df.columns]
    df["Year"] = df["Year"].astype(int)
    return df

plot_df = load_data()

# ---------------------------------------------------------------------------
# Extract config values 
# ---------------------------------------------------------------------------

MUNICIPALITIES = sorted(plot_df["Municipality"].unique().tolist())
START_YEAR = int(plot_df["Year"].min())
END_YEAR = int(plot_df["Year"].max())
PROPERTY_CLASSES = [
    col.replace(" Tax Rate", "")
    for col in plot_df.columns
    if col.endswith(" Tax Rate")
]

DEFAULT_MUNIS = ["Squamish", "Whistler", "Pemberton"]

_latest_pop = (
    plot_df[plot_df["Year"] == END_YEAR][["Municipality", "Population"]]
    .dropna()
    .set_index("Municipality")["Population"]
    .astype(int)
)
POP_MIN = int(_latest_pop.min() // 1000 * 1000)
POP_MAX = int((_latest_pop.max() + 999) // 1000 * 1000)

_latest_thv = (
    plot_df[plot_df["Year"] == END_YEAR][["Municipality", "Typical House Value"]]
    .dropna()
    .set_index("Municipality")["Typical House Value"]
    .astype(int)
)
THV_MIN = int(_latest_thv.min() // 100_000 * 100_000)
THV_MAX = int((_latest_thv.max() + 99_999) // 100_000 * 100_000)

OVERVIEW_VARS = [
    "Population",
    "Total Taxable Value",
    "Total Taxes Collected",
    "Tax per Capita",
    "Typical House Value",
    "School Tax on Typical House",
    "General Municipal Tax on Typical House",
    "Regional District Tax on Typical House",
    "Hospital Tax on Typical House",
    "Other Tax on Typical House",
    "Total Variable Rate Taxes on Typical House",
    "Total Property Taxes and Charges on Typical House",
]

PLOT_VARS = OVERVIEW_VARS + [
    col for col in plot_df.columns
    if col.endswith((" Tax Rate", " Taxable Value", " Tax Multiple"))
]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

ui.page_opts(title="BC Municipal Tax Dashboard", fillable=False)
ui.include_css(Path(__file__).parent / "styles.css")



with ui.sidebar():
    ui.h6(
    "Explore property tax data for BC municipalities. "
    ),

    ui.hr()
    ui.h6("Selected Municipalities")
    ui.input_selectize(
        "municipalities",
        None,
        choices=MUNICIPALITIES,
        selected=DEFAULT_MUNIS,
        multiple=True,
        width="100%",
    )

    ui.hr()

    ui.markdown("Filter municipalies by Population, Typical House Value, or manually select by name above.")
    ui.input_radio_buttons(
        "filter_type",
        "",
        choices={"none": "Manual Selection", "pop": "Population", "thv": "Typical House Value"},
        selected="none",
    )
    with ui.panel_conditional("input.filter_type === 'pop'"):
        ui.input_slider(
            "pop_range",
            None,
            min=POP_MIN,
            max=POP_MAX,
            value=[20_000, 30_000],
            step=5000,
            sep=",",
            width="100%",
        )
    with ui.panel_conditional("input.filter_type === 'thv'"):
        ui.input_slider(
            "thv_range",
            None,
            min=THV_MIN,
            max=THV_MAX,
            value=[1_000_000, 1_200_000],
            step=100_000,
            pre="$",
            sep=",",
            width="100%",
        )
    ui.hr()

    ui.markdown(
        "Data is sourced from the [Province of BC Tax Rates and Burdens](https://www2.gov.bc.ca/gov/content/governments/local-governments/facts-framework/statistics/tax-rates-tax-burden) Schedule 707 and Schedule 704 reports. "
    ),

    ui.markdown(
        "Dashboard by Andrew Hamilton, [Computing & Data Science at Capilano University](https://www.capilanou.ca/programs--courses/search--select/explore-our-areas-of-study/arts--sciences/school-of-science-technology-engineering--mathematics-stem/computing--data-science-department/).  "
    ),
    ui.markdown(
        "Contact via [Linkedin](https://www.linkedin.com/in/andrew-hamilton-phd/) or [email](mailto:andrew@bcmunicipaldata.org).  "
    ),
    ui.markdown(
        "Source code available at [Hamilton-at-CapU on GitHub](https://github.com/Hamilton-at-CapU/muni-tax-dashboard).  "
    ),



@reactive.effect
def _sync_muni_filter():
    filter_type = input.filter_type()
    if filter_type == "pop":
        lo, hi = input.pop_range()
        in_range = _latest_pop[(_latest_pop >= lo) & (_latest_pop <= hi)].index.tolist()
    elif filter_type == "thv":
        lo, hi = input.thv_range()
        in_range = _latest_thv[(_latest_thv >= lo) & (_latest_thv <= hi)].index.tolist()
    else:
        return
    ui.update_selectize("municipalities", selected=sorted(in_range))


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

with ui.navset_tab():

    with ui.nav_panel("Time Trend"):
        with ui.card(full_screen=True, style="height:calc(100vh - 160px)"):
            with ui.card_header(class_="d-flex align-items-center gap-2"):
                ui.span("Trend: ")
                ui.input_select(
                    "trend_var",
                    None,
                    choices=PLOT_VARS,
                    selected="Tax per Capita",
                    width="auto",
                )
                ui.span(" for years: ")
                ui.input_slider(
                    "years",
                    None,
                    min=START_YEAR,
                    max=END_YEAR,
                    value=[START_YEAR, END_YEAR],
                    step=1,
                    sep="",
                    width="300px",
                )

            @render_plotly
            def trend_chart():
                col = input.trend_var()
                d = (
                    filtered_df()
                    [["Year", "Municipality", col]]
                    .dropna()
                )
                fig = px.line(
                    d, x="Year", y=col, color="Municipality",
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.D3,
                )
                fig.update_layout(
                    legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title=input.trend_var(),
                )
                return fig

    with ui.nav_panel("Property Class Breakdown"):
        with ui.card(full_screen=True, style="height:calc(100vh - 160px)"):
            with ui.card_header(class_="d-flex align-items-center gap-2"):
                ui.span("Breakdown of :")
                ui.input_select(
                    "breakdown_metric",
                    None,
                    choices=["Tax Rate", "Tax Multiple", "Taxable Value"],
                    selected="Tax Rate",
                    width="auto",
                )
                ui.span(" for year: ")
                ui.input_select(
                    "breakdown_year",
                    None,
                    choices=[str(y) for y in range(START_YEAR, END_YEAR + 1)],
                    selected=str(END_YEAR),
                    width="auto",
                )

            @render_plotly
            def breakdown_chart():
                req(input.municipalities())
                metric = input.breakdown_metric()
                year = int(input.breakdown_year())
                metric_cols = [c + f" {metric}" for c in PROPERTY_CLASSES]
                cols = ["Municipality"] + metric_cols
                munis = input.municipalities()
                d = plot_df[
                    plot_df["Municipality"].isin(munis) &
                    (plot_df["Year"] == year)
                ][cols].dropna(how="all", subset=metric_cols)
                d_long = d.melt(
                    id_vars="Municipality",
                    var_name="Property Class",
                    value_name=metric,
                )
                d_long["Property Class"] = d_long["Property Class"].str.replace(
                    f" {metric}", "", regex=False
                )
                y_labels = {
                    "Tax Rate":      "Tax Rate ($ per $1,000)",
                    "Tax Multiple":  "Tax Multiple",
                    "Taxable Value": "Taxable Value ($)",
                }
                fig = px.bar(
                    d_long, x="Municipality", y=metric,
                    color="Property Class",
                    barmode="group",
                    color_discrete_sequence=px.colors.qualitative.D3,
                )
                fig.update_layout(
                    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title=y_labels[metric],
                )
                return fig

    with ui.nav_panel("Comparative Distribution"):
        with ui.card(full_screen=True, style="height:calc(100vh - 160px)"):
            with ui.card_header(class_="d-flex align-items-center gap-2 flex-wrap"):
                ui.span("Distribution of")
                ui.input_select(
                    "density_var",
                    None,
                    choices=PLOT_VARS,
                    selected="Tax per Capita",
                    width="auto",
                )
                ui.span(" for year: ")
                ui.input_select(
                    "density_year",
                    None,
                    choices=[str(y) for y in range(START_YEAR, END_YEAR + 1)],
                    selected=str(END_YEAR),
                    width="auto",
                )
                ui.span(" | ")

                @render.ui
                def density_avg_boxes():
                    col = input.density_var()
                    year = int(input.density_year())
                    munis = input.municipalities()

                    all_d = plot_df[plot_df["Year"] == year][col].dropna()
                    all_d = all_d[all_d != 0]
                    sel_d = plot_df[
                        (plot_df["Year"] == year) &
                        (plot_df["Municipality"].isin(munis))
                    ][col].dropna()

                    def fmt(val):
                        if pd.isna(val):
                            return "N/A"
                        if abs(val) >= 1_000_000:
                            return f"${val/1_000_000:.2f}M"
                        if abs(val) >= 1_000:
                            return f"${val:,.0f}"
                        return f"{val:,.2f}"

                    all_avg  = all_d.mean()  if not all_d.empty  else float("nan")
                    sel_avg  = sel_d.mean()  if not sel_d.empty  else float("nan")

                    return ui.TagList(
                        ui.tags.span(
                            ui.tags.small("All municipalities avg: ",
                                          style="opacity:.7;"),
                            ui.tags.strong(fmt(all_avg)),
                            class_="badge text-bg-secondary me-1 fw-normal fs-6 px-2 py-1",
                        ),
                        ui.tags.span(
                            ui.tags.small("Selected avg: ",
                                          style="opacity:.7;"),
                            ui.tags.strong(fmt(sel_avg)),
                            class_="badge text-bg-primary fw-normal fs-6 px-2 py-1",
                        ),
                    )

            ui.card_footer(
                "Density distribution includes all municipalities."
            )

            @render_plotly
            def density_chart():
                munis = req(input.municipalities())
                col = input.density_var()
                year = int(input.density_year())

                all_d = plot_df[plot_df["Year"] == year][["Municipality", col]].dropna()
                if all_d.empty:
                    return go.Figure()

                values = all_d[col].values

                # KDE via numpy histogram as a smooth curve
                x_min, x_max = values.min(), values.max()
                x_range = np.linspace(x_min, x_max, 300)

                bw = 1.06 * values.std() * len(values) ** -0.2  # Silverman's rule
                kde_y = np.array([
                    np.mean(np.exp(-0.5 * ((x - values) / bw) ** 2) / (bw * np.sqrt(2 * np.pi)))
                    for x in x_range
                ])

                fig = make_subplots(
                    rows=2, cols=1,
                    row_heights=[0.85, 0.15],
                    shared_xaxes=True,
                    vertical_spacing=0.02,
                )

                # KDE curve
                fig.add_trace(go.Scatter(
                    x=x_range,
                    y=kde_y,
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color="rgba(99,110,250,0.8)", width=2),
                    fillcolor="rgba(99,110,250,0.15)",
                    name="All municipalities",
                    hoverinfo="skip",
                ), row=1, col=1)

                colors = px.colors.qualitative.D3
                selected_rows = all_d[all_d["Municipality"].isin(munis)]

                # Vertical lines + annotations for selected municipalities
                for i, (_, row) in enumerate(selected_rows.iterrows()):
                    muni = row["Municipality"]
                    val = row[col]
                    pct = (values < val).mean() * 100
                    color = colors[i % len(colors)]

                    fig.add_vline(
                        x=val,
                        line=dict(color=color, width=2, dash="dash"),
                        row=1, col=1,
                    )
                    fig.add_annotation(
                        x=val,
                        y=kde_y.max(),
                        text=f"{muni}<br>({pct:.0f}th pct)",
                        showarrow=True,
                        arrowhead=2,
                        arrowcolor=color,
                        font=dict(size=11, color=color),
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor=color,
                        ax=0,
                        ay=-36,
                        xref="x", yref="y",
                    )

                # 1D rug — all municipalities in grey
                fig.add_trace(go.Scatter(
                    x=all_d[col],
                    y=np.zeros(len(all_d)),
                    mode="markers",
                    marker=dict(
                        symbol="line-ns",
                        size=12,
                        color="rgba(150,150,150,0.4)",
                        line=dict(color="rgba(150,150,150,0.4)", width=1),
                    ),
                    text=all_d["Municipality"],
                    hovertemplate="%{text}: %{x}<extra></extra>",
                    name="All municipalities",
                    showlegend=False,
                ), row=2, col=1)

                # 1D rug — selected municipalities highlighted
                for i, (_, row) in enumerate(selected_rows.iterrows()):
                    muni = row["Municipality"]
                    val = row[col]
                    color = colors[i % len(colors)]

                    fig.add_trace(go.Scatter(
                        x=[val],
                        y=[0],
                        mode="markers",
                        marker=dict(
                            symbol="line-ns",
                            size=16,
                            color=color,
                            line=dict(color=color, width=2),
                        ),
                        name=muni,
                        hovertemplate=f"{muni}: {val:.1f}<extra></extra>",
                        showlegend=False,
                    ), row=2, col=1)

                fig.update_layout(
                    xaxis2_title=input.density_var(),
                    yaxis_title="Density",
                    showlegend=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                fig.update_yaxes(visible=False, row=2, col=1)
                fig.update_xaxes(showticklabels=True, row=2, col=1)

                return fig

    with ui.nav_panel("Map"):
        with ui.card(full_screen=True, style="height:calc(100vh - 160px)"):
            with ui.card_header(class_="d-flex align-items-center gap-2"):
                ui.span("Map: ")
                ui.input_select(
                    "map_var",
                    None,
                    choices=PLOT_VARS,
                    selected="Tax per Capita",
                    width="auto",
                )
                ui.span(" for year: ")
                ui.input_select(
                    "map_year",
                    None,
                    choices=[str(y) for y in range(START_YEAR, END_YEAR + 1)],
                    selected=str(END_YEAR),
                    width="auto",
                )

            @render_plotly
            def map_chart():
                col = input.map_var()
                year = int(input.map_year())
                selected_munis = input.municipalities()

                d = plot_df[plot_df["Year"] == year][["Municipality", col]].dropna()
                d = d.copy()
                d["lat"] = d["Municipality"].map(lambda m: MUNI_COORDS.get(m, (None, None))[0])
                d["lon"] = d["Municipality"].map(lambda m: MUNI_COORDS.get(m, (None, None))[1])
                d = d.dropna(subset=["lat", "lon"])
                d["Selected"] = d["Municipality"].isin(selected_munis)

                fig = px.scatter_mapbox(
                    d,
                    lat="lat",
                    lon="lon",
                    color=col,
                    size=col,
                    size_max=30,
                    hover_name="Municipality",
                    hover_data={col: True, "lat": False, "lon": False},
                    color_continuous_scale="Viridis",
                    zoom=4,
                    center={"lat": 54.0, "lon": -124.0},
                    mapbox_style="carto-positron",
                )

                # Add a highlighted ring around selected municipalities
                sel = d[d["Selected"]]
                if not sel.empty:
                    fig.add_trace(go.Scattermapbox(
                        lat=sel["lat"],
                        lon=sel["lon"],
                        mode="markers",
                        marker=dict(size=18, color="rgba(0,0,0,0)", symbol="circle"),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_colorbar=dict(title=col),
                    uirevision="map",
                    modebar=dict(
                        add=["zoomin", "zoomout", "resetview"],
                        orientation="v",
                    ),
                )
                return fig


# ---------------------------------------------------------------------------
# Reactive data
# ---------------------------------------------------------------------------

@reactive.calc
def filtered_df():
    munis = req(input.municipalities())
    yr = input.years()
    return plot_df[
        plot_df["Municipality"].isin(munis) &
        plot_df["Year"].between(yr[0], yr[1])
    ]


@reactive.calc
def latest_df():
    yr = input.years()
    d = filtered_df()
    if d.empty:
        return d
    max_yr = min(yr[1], d["Year"].max())
    return d[d["Year"] == max_yr]

