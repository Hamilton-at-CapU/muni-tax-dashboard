from pathlib import Path
import json
import pandas as pd
import plotly.express as px
from shiny import reactive, req
from shiny.express import input, render, ui
from shinywidgets import render_plotly

from config import MUNICIPALITIES, START_YEAR, END_YEAR, PROPERTY_CLASSES

# ---------------------------------------------------------------------------
# Column groups exposed to plot_data
# ---------------------------------------------------------------------------

# Human-readable label -> actual column name
PLOT_VARIABLES: dict[str, str] = {
    # --- Overview ---
    'Population':                          'Population',
    'Total Taxable Value':                 'Total Taxable Value',
    'Total Taxes Collected':               'Total Taxes Collected',
    'Tax per Capita':                      'Tax per Capita',
    'House Value':                         'House Value',
    'Total Variable Rate Taxes':           'Total Variable Rate Taxes',
    'Total Property Taxes and Charges':    'Total Property Taxes and Charges',
    # --- Property class tax rates ---
    'Residential Tax Rate':                'Residential Tax Rate',
    'Utilities Tax Rate':                  'Utilities Tax Rate',
    'Major Industry Tax Rate':             'Major Industry Tax Rate',
    'Light Industry Tax Rate':             'Light Industry Tax Rate',
    'Business/Other Tax Rate':             'Business/Other Tax Rate',
    'Managed Forest Tax Rate':             'Managed Forest Tax Rate',
    'Recreation Tax Rate':                 'Recreation Tax Rate',
    'Farm Tax Rate':                       'Farm Tax Rate',
    # --- Property class taxable values ---
    'Residential Taxable Value':           'Residential Taxable Value',
    'Utilities Taxable Value':             'Utilities Taxable Value',
    'Major Industry Taxable Value':        'Major Industry Taxable Value',
    'Light Industry Taxable Value':        'Light Industry Taxable Value',
    'Business/Other Taxable Value':        'Business/Other Taxable Value',
    'Managed Forest Taxable Value':        'Managed Forest Taxable Value',
    'Recreation Taxable Value':            'Recreation Taxable Value',
    'Farm Taxable Value':                  'Farm Taxable Value',
    # --- Property class tax multiples ---
    'Residential Tax Multiple':            'Residential Tax Multiple',
    'Utilities Tax Multiple':              'Utilities Tax Multiple',
    'Major Industry Tax Multiple':         'Major Industry Tax Multiple',
    'Light Industry Tax Multiple':         'Light Industry Tax Multiple',
    'Business/Other Tax Multiple':         'Business/Other Tax Multiple',
    'Managed Forest Tax Multiple':         'Managed Forest Tax Multiple',
    'Recreation Tax Multiple':             'Recreation Tax Multiple',
    'Farm Tax Multiple':                   'Farm Tax Multiple',
}


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_data(path: str | Path = 'data.json') -> pd.DataFrame:
    """Load data.json into a flat DataFrame.

    Top-level scalar fields become columns directly.
    Nested Property Classes are flattened to columns like:
        'Residential Tax Rate', 'Residential Taxable Value', 'Residential Tax Multiple', ...
    """
    with open(path) as f:
        records = json.load(f)

    rows = []
    for r in records:
        row = {
            'Year':                             r['Year'],
            'Municipality':                     r['Municipality'],
            'Population':                       r.get('Population'),
            'Total Taxable Value':              r.get('Total Taxable Value'),
            'Total Taxes Collected':            r.get('Total Taxes Collected'),
            'Tax per Capita':                   r.get('Tax per Capita'),
            'House Value':                      r.get('House Value'),
            'Total Variable Rate Taxes':        r.get('Total Variable Rate Taxes'),
            'Total Property Taxes and Charges': r.get('Total Property Taxes and Charges'),
        }
        for cls, vals in (r.get('Property Classes') or {}).items():
            if vals is None:
                continue
            row[f'{cls} Taxable Value'] = vals.get('Taxable Value')
            row[f'{cls} Tax Rate']      = vals.get('Tax Rate')
            row[f'{cls} Tax Multiple']  = vals.get('Tax Multiple')
        rows.append(row)

    df = pd.DataFrame(rows)
    df['Year'] = df['Year'].astype(int)
    return df





# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

app_dir = Path(__file__).parent
#plot_df = load_data(app_dir / "data.json")

curr_dir = Path(__file__).cwd()
plot_df = load_data(curr_dir / "data.json")

YEAR_MIN = START_YEAR
YEAR_MAX = END_YEAR

DEFAULT_MUNIS = ["Squamish", "Whistler", "Pemberton"]

OVERVIEW_VARS = [
    "Population",
    "Total Taxable Value",
    "Total Taxes Collected",
    "Tax per Capita",
    "House Value",
    "Total Variable Rate Taxes",
    "Total Property Taxes and Charges",
]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

ui.page_opts(title="BC Municipal Tax Dashboard", fillable=True)
ui.include_css(app_dir / "styles.css")

with ui.sidebar():
    ui.h6("Municipalities")
    ui.input_selectize(
        "municipalities",
        None,
        choices=MUNICIPALITIES,
        selected=DEFAULT_MUNIS,
        multiple=True,
        width="100%",
    )
    ui.hr()
    ui.h6("Year range")
    ui.input_slider(
        "years",
        None,
        min=YEAR_MIN,
        max=YEAR_MAX,
        value=[YEAR_MIN, YEAR_MAX],
        step=1,
        sep="",
    )
    ui.hr()
    ui.h6("Trend variable")
    ui.input_select(
        "trend_var",
        None,
        choices=OVERVIEW_VARS,
        selected="Tax per Capita",
    )
    ui.hr()
    ui.h6("Property class")
    ui.input_select(
        "prop_class",
        None,
        choices=PROPERTY_CLASSES,
        selected="Residential",
    )

# ---------------------------------------------------------------------------
# Value boxes — snapshot for the most recent year selected
# ---------------------------------------------------------------------------

with ui.layout_columns(col_widths={"sm": 6, "md": 3}, class_="value-box-grid"):

    with ui.value_box(showcase=ui.tags.i(class_="bi bi-people-fill"), theme="primary"):
        "Population"
        @render.text
        def vb_population():
            d = latest_df()
            if d.empty:
                return "—"
            total = d["Population"].sum()
            return f"{total:,.0f}"

    with ui.value_box(showcase=ui.tags.i(class_="bi bi-house-fill"), theme="success"):
        "Avg House Value"
        @render.text
        def vb_house():
            d = latest_df()
            if d.empty:
                return "—"
            val = d["House Value"].mean()
            return "—" if val != val else f"${val:,.0f}"

    with ui.value_box(showcase=ui.tags.i(class_="bi bi-cash-stack"), theme="warning"):
        "Avg Tax per Capita"
        @render.text
        def vb_tax_capita():
            d = latest_df()
            if d.empty:
                return "—"
            val = d["Tax per Capita"].mean()
            return "—" if val != val else f"${val:,.0f}"

    with ui.value_box(showcase=ui.tags.i(class_="bi bi-building"), theme="danger"):
        "Avg Residential Tax Rate"
        @render.text
        def vb_res_rate():
            d = latest_df()
            if d.empty:
                return "—"
            val = d["Residential Tax Rate"].mean()
            return "—" if val != val else f"{val:.4f}"

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

with ui.layout_columns(col_widths={"sm": 12, "lg": [7, 5]}):

    with ui.card(full_screen=True):
        with ui.card_header():
            @render.text
            def trend_header():
                return input.trend_var() + " over time"

        @render_plotly
        def trend_chart():
            munis = req(input.municipalities())
            col = PLOT_VARIABLES[input.trend_var()]
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

    with ui.card(full_screen=True):
        with ui.card_header():
            @render.text
            def rate_header():
                return input.prop_class() + " Tax Rate over time"

        @render_plotly
        def rate_chart():
            munis = req(input.municipalities())
            col = input.prop_class() + " Tax Rate"
            d = filtered_df()[["Year", "Municipality", col]].dropna()
            fig = px.line(
                d, x="Year", y=col, color="Municipality",
                markers=True,
                color_discrete_sequence=px.colors.qualitative.D3,
            )
            fig.update_layout(
                legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="Tax Rate ($ per $1,000)",
            )
            return fig

with ui.layout_columns(col_widths={"sm": 12, "lg": [5, 7]}):

    with ui.card(full_screen=True):
        with ui.card_header():
            @render.text
            def multiple_header():
                return input.prop_class() + " Tax Multiples — latest year"

        @render_plotly
        def multiple_chart():
            req(input.municipalities())
            col = input.prop_class() + " Tax Multiple"
            d = latest_df()[["Municipality", col]].dropna().sort_values(col)
            fig = px.bar(
                d, x=col, y="Municipality", orientation="h",
                color="Municipality",
                color_discrete_sequence=px.colors.qualitative.D3,
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Tax Multiple",
            )
            return fig

    with ui.card(full_screen=True):
        ui.card_header("Tax Breakdown — latest year")

        @render_plotly
        def breakdown_chart():
            req(input.municipalities())
            rate_cols = [c + " Tax Rate" for c in PROPERTY_CLASSES]
            cols = ["Municipality"] + rate_cols
            d = latest_df()[cols].dropna(how="all", subset=rate_cols)
            d_long = d.melt(
                id_vars="Municipality",
                var_name="Property Class",
                value_name="Tax Rate",
            )
            d_long["Property Class"] = d_long["Property Class"].str.replace(
                " Tax Rate", "", regex=False
            )
            fig = px.bar(
                d_long, x="Municipality", y="Tax Rate",
                color="Property Class",
                barmode="group",
                color_discrete_sequence=px.colors.qualitative.D3,
            )
            fig.update_layout(
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="Tax Rate ($ per $1,000)",
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