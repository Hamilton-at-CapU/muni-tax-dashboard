# BC Municipal Tax Dashboard

An interactive Shiny for Python dashboard for exploring property tax data across BC municipalities from 2005 to 2025.

## Live App

The app is deployed via Shinylive at the project's GitHub Pages URL, and from [www.bcmunicipaldata.org](www.bcmunicipaldata.org)

## Features

- **Trend chart** — plot any variable over time for selected municipalities
- **Property class breakdown** — tax rates, taxable values, and tax multiples by property class
- **Distribution chart** — KDE density plot showing where selected municipalities sit relative to all others in a given year
- **Sidebar filters** — filter municipalities by population or typical house value using a range slider, or select manually

## Project Structure

```
muni-tax-dashboard/
├── app/
│   ├── app.py          # Shiny app
│   ├── data.json       # Pre-processed data used by the app
│   └── styles.css      # Custom CSS
├── data_prep/
│   ├── prep.py         # Data extraction and processing script
│   ├── data.json       # Output from prep.py (copied to app/)
│   └── raw_data/       # Raw Excel files from [https://www2.gov.bc.ca/gov/content/governments/local-governments/facts-framework/statistics/tax-rates-tax-burden](Schedule 707 and 704) are not included in GitHub, download them if you need to rebuild data.json
├── docs/               # Shinylive build output (GitHub Pages)
├── requirements.txt
└── pyproject.toml
```

## Data Sources

Data is extracted from BC Ministry of Municipal Affairs annual reports:

- **Schedule 707** — Municipal Tax Rates: population, total taxable value, total taxes collected, tax per capita, and per-property-class tax rates, taxable values, and tax multiples
- **Schedule 704** — Tax Burden: typical house value, school tax, general municipal tax, regional district tax, hospital tax, other tax, total variable rate taxes, and total property taxes and charges

Source: https://www2.gov.bc.ca/gov/content/governments/local-governments/facts-framework/statistics/tax-rates-tax-burden

## Updating the Data

1. Download the latest Schedule 707 and 704 Excel files into `data_prep/raw_data/`
2. Run the prep script:
   ```bash
   python data_prep/prep.py
   ```
3. Copy the output to the app:
   ```bash
   cp data_prep/data.json app/data.json
   ```

## Running Locally

Install dependencies and run the app:

```bash
pip install -r requirements.txt
shiny run app/app.py
```

## Dependencies

Key packages:

| Package | Purpose |
|---------|---------|
| `shiny` | App framework |
| `shinywidgets` | Plotly widget integration |
| `plotly` | Interactive charts |
| `pandas` | Data manipulation |
| `numpy` | Numerical operations |
| `openpyxl` / `xlrd` | Reading raw Excel files in `prep.py` |

## License

See [LICENSE](LICENSE).
