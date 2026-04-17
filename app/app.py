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
    'Typical House Value':                               'Typical House Value',
    'School Tax on Typical House':                       'School Tax on Typical House',
    'General Municipal Tax on Typical House':            'General Municipal Tax on Typical House',
    'Regional District Tax on Typical House':            'Regional District Tax on Typical House',
    'Hospital Tax on Typical House':                     'Hospital Tax on Typical House',
    'Other Tax on Typical House':                        'Other Tax on Typical House',
    'Total Variable Rate Taxes on Typical House':        'Total Variable Rate Taxes on Typical House',
    'Total Property Taxes and Charges on Typical House': 'Total Property Taxes and Charges on Typical House',
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
            'Typical House Value':              r.get('Typical House Value'),
            'School Tax on Typical House':                       r.get('School Tax on Typical House'),
            'General Municipal Tax on Typical House':            r.get('General Municipal Tax on Typical House'),
            'Regional District Tax on Typical House':            r.get('Regional District Tax on Typical House'),
            'Hospital Tax on Typical House':                     r.get('Hospital Tax on Typical House'),
            'Other Tax on Typical House':                        r.get('Other Tax on Typical House'),
            'Total Variable Rate Taxes on Typical House':        r.get('Total Variable Rate Taxes on Typical House'),
            'Total Property Taxes and Charges on Typical House': r.get('Total Property Taxes and Charges on Typical House'),
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

try:
    app_dir = Path(__file__).parent
    plot_df = load_data(app_dir / "data.json")
except (NameError, FileNotFoundError):
    plot_df = load_data("data.json")

YEAR_MIN = START_YEAR
YEAR_MAX = END_YEAR

DEFAULT_MUNIS = ["Squamish", "Whistler", "Pemberton"]

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



# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

with ui.layout_columns(col_widths=12):
    with ui.card(full_screen=True):
        with ui.card_header(class_="d-flex align-items-center gap-2"):
            ui.span("Trend: ")
            ui.input_select(
                "trend_var",
                None,
                choices=list(PLOT_VARIABLES.keys()),
                selected="Tax per Capita",
                width="auto",
            )
            ui.span(" for years: ")
            ui.input_slider(
                "years",
                None,
                min=YEAR_MIN,
                max=YEAR_MAX,
                value=[YEAR_MIN, YEAR_MAX],
                step=1,
                sep="",
                width="300px",
            )

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

with ui.layout_columns(col_widths=12):

    with ui.card(full_screen=True):
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

# ---------------------------------------------------------------------------
# Density plot — distribution across all municipalities for a single year
# ---------------------------------------------------------------------------

with ui.layout_columns(col_widths=12):
    with ui.card(full_screen=True):
        with ui.card_header(class_="d-flex align-items-center gap-2 flex-wrap"):
            ui.span("Distribution of")
            ui.input_select(
                "density_var",
                None,
                choices=list(PLOT_VARIABLES.keys()),
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
                col = PLOT_VARIABLES[input.density_var()]
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
            col = PLOT_VARIABLES[input.density_var()]
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