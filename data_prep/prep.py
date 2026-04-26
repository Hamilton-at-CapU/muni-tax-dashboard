"""  
Extract data from BC Municipal Tax Rates and Tax Burden Schedules 704 and 707 
available at: 
https://www2.gov.bc.ca/gov/content/governments/local-governments/facts-framework/statistics/tax-rates-tax-burden

Fields extracted:
  From Schedule 707 (Totals row):
    - Population
    - Total Taxable Value
    - Total Taxes Collected
    - Tax per Capita

  From Schedule 707 (per Property Class row):
    - Taxable Value
    - Tax Rate
    - Tax Class Multiple

  From Schedule 707 (per Property Class, nested under 'Property Classes'):

  From Schedule 704 (municipality row):
    - House Value
    - Total Variable Rate Taxes
    - House Value
    - School Tax
    - General Municipal Tax
    - Regional District Tax
    - Hospital Tax
    - Other Tax
    - Total Variable Rate Taxes
    - Total Property Taxes and Charges
"""

import json
import pandas as pd
from pathlib import Path
from config import MUNICIPALITIES, START_YEAR, END_YEAR, PROPERTY_CLASSES

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path('.')
RAW_DATA_DIR = DATA_DIR / 'data_prep/raw_data/'
OUTPUT_FILE = DATA_DIR / 'data_prep/data.json'



# ---------------------------------------------------------------------------
# Schedule 707 helpers
# ---------------------------------------------------------------------------

# Municipalities that exist as both a City and a District in the source data.
# The raw type column contains 'C' (City) or 'D' (District).
_AMBIGUOUS = {'Langley', 'North Vancouver'}
_TYPE_SUFFIX = {'C': ' (City)', 'D': ' (District)'}

# Known municipality name variations across years, mapped to their canonical form.
_NAME_ALIASES = {
    "Abbotsford - C": "Abbotsford",
    "Queen Charlotte": "Daajing Giids",
    "Northern Rockies - REGM": "Northern Rockies"
}

def _disambiguate(df: pd.DataFrame, muni_col: int = 0, type_col: int = 1) -> None:
    """Append ' (City)' or ' (District)' to ambiguous municipality names in-place.

    Works on a raw DataFrame (integer-indexed columns) before column renaming.
    """
    muni = df.iloc[:, muni_col]
    typ  = df.iloc[:, type_col].astype(str).str.strip()
    mask = muni.isin(_AMBIGUOUS)
    df.iloc[mask.values, muni_col] = muni[mask] + typ[mask].map(_TYPE_SUFFIX).fillna('')


def scrape_707(year: int, municipalities: list[str]) -> dict:
    """Return a dict of {municipality: dict} with Totals-row and per-class fields from Schedule 707.

    Schedule 707 column positions (0-indexed, consistent across all years):
      0  - Municipality name (label varies: 'Municipality', 'Municipalities', etc.)
      3  - Population (label varies by year)
      4  - Property Class
      5  - Authenticated Roll General Taxable Values
      6  - Municipal Purposes Tax Rates
      7  - Tax Class Multiples
      10 - Total Municipal Taxes
      13 - Municipal Taxes Per Capita

    Note: 2005 and 2006 files have only one row per municipality (Residential only, no Totals row).
    In that case, aggregate values are read directly from that single row.
    """

    path = RAW_DATA_DIR / (f'schedule707_{year}.xlsx' if year > 2019 else f'schedule707_{year}.xls')

    # Read by column index to avoid year-varying header names.
    # Column 1 is the municipality type (C=City, D=District) — needed to
    # disambiguate Langley and North Vancouver before we drop it.
    df = pd.read_excel(path, header=1, usecols=[0, 1, 3, 4, 5, 6, 7, 10, 13])

    # Forward-fill the municipality column — older files only populate it on the
    # first (Residential) row; subsequent property class rows are blank.
    df.iloc[:, 0] = df.iloc[:, 0].ffill()
    df.iloc[:, 1] = df.iloc[:, 1].ffill()

    # Strip leading/trailing whitespace from municipality names
    df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()

    # Normalise known name variations to their canonical form
    df.iloc[:, 0] = df.iloc[:, 0].replace(_NAME_ALIASES)

    # Append (City)/(District) suffix to ambiguous municipality names, then drop type col.
    _disambiguate(df, muni_col=0, type_col=1)
    df.drop(columns=df.columns[1], inplace=True)

    # Normalise column names
    cols = df.columns.tolist()
    muni_col       = cols[0]   # 'Municipality', 'Municipalities', 'Municipalities1', etc.
    pop_col        = cols[1]   # 'July 1, 20XX BC STATS Population Estimates...'
    prop_class_col = cols[2]   # 'Property Class'

    df.rename(columns={
        muni_col: 'Municipality',
        pop_col:  'Population',
        cols[3]:  'Taxable Value',
        cols[4]:  'Tax Rate',
        cols[5]:  'Tax Class Multiple',
        cols[6]:  'Total Taxes Collected',
        cols[7]:  'Tax per Capita',
    }, inplace=True)

    result = {}
    for muni in municipalities:
        muni_df = df[df['Municipality'] == muni].copy()
        if muni_df.empty:
            continue
        muni_df.set_index(prop_class_col, inplace=True)

        # Normalise index labels that vary across years
        muni_df.rename(index={'Business': 'Business/Other'}, inplace=True)

        # --- Totals row (aggregate fields) ---
        if 'Totals' in muni_df.index:
            totals = muni_df.loc['Totals']
        else:
            totals = muni_df.iloc[0]

        # Population is most reliably on the Residential row; fall back to Totals
        if 'Residential' in muni_df.index:
            population = _int(muni_df.loc['Residential'].get('Population'))
        else:
            population = None
        if population is None:
            population = _int(totals.get('Population'))

        row = {
            'Population':            population,
            'Total Taxable Value':   _int(totals.get('Taxable Value')),
            'Total Taxes Collected': _int(totals.get('Total Taxes Collected')),
            'Tax per Capita':        _int(totals.get('Tax per Capita')),
        }

        # --- Per-class fields — stored as a nested object ---
        property_classes = {}
        for prop_class in PROPERTY_CLASSES:
            if prop_class in muni_df.index:
                class_row = muni_df.loc[prop_class]
                property_classes[prop_class] = {
                    'Taxable Value':    _int(class_row.get('Taxable Value')),
                    'Tax Rate':         _val(class_row.get('Tax Rate')),
                    'Tax Multiple':     _val(class_row.get('Tax Class Multiple')),
                }
            else:
                property_classes[prop_class] = None

        row['Property Classes'] = property_classes
        result[muni] = row

    return result


# ---------------------------------------------------------------------------
# Schedule 704 helpers
# ---------------------------------------------------------------------------

def scrape_704(year: int, municipalities: list[str]) -> dict:
    """Return a dict of {municipality: dict} with representative house fields from Schedule 704.

    Schedule 704 column layout:
      0  - Municipalities
      1  - Type
      2  - RD
      3  - House Value
      4  - School
      5  - General Municipal Total
      6  - Regional District
      7  - Hospital
      8  - BCA, MFA and Other
      9  - Total Res Variable Rate Taxes
      10 - Total Res Parcel Taxes
      11 - Total Res. User Fees
      12 - Total Residential Property Taxes and Charges
    """
    path = RAW_DATA_DIR / (f'schedule704_{year}.xlsx' if year > 2019 else f'schedule704_{year}.xls')

    # Column 1 is the municipality type (C=City, D=District) — needed to
    # disambiguate Langley and North Vancouver before we drop it.
    df = pd.read_excel(path, header=1, usecols=[0, 1, 3, 4, 5, 6, 7, 8, 9, 12])

    # Append (City)/(District) suffix to ambiguous municipality names, then drop type col.
    _disambiguate(df, muni_col=0, type_col=1)
    df.drop(columns=df.columns[1], inplace=True)

    cols = df.columns.tolist()
    df.rename(columns={
        cols[0]: 'Municipality',
        cols[1]: 'House Value',
        cols[2]: 'School Tax',
        cols[3]: 'General Municipal Tax',
        cols[4]: 'Regional District Tax',
        cols[5]: 'Hospital Tax',
        cols[6]: 'Other Tax',
        cols[7]: 'Total Variable Rate Taxes',
        cols[8]: 'Total Property Taxes and Charges',
    }, inplace=True)

    result = {}
    for muni in municipalities:
        row = df[df['Municipality'] == muni]
        if row.empty:
            continue
        row = row.iloc[0]
        result[muni] = {
            'Typical House Value':                               _int(row.get('House Value')),
            'School Tax on Typical House':                       _int(row.get('School Tax')),
            'General Municipal Tax on Typical House':            _int(row.get('General Municipal Tax')),
            'Regional District Tax on Typical House':            _int(row.get('Regional District Tax')),
            'Hospital Tax on Typical House':                     _int(row.get('Hospital Tax')),
            'Other Tax on Typical House':                        _int(row.get('Other Tax')),
            'Total Variable Rate Taxes on Typical House':        _int(row.get('Total Variable Rate Taxes')),
            'Total Property Taxes and Charges on Typical House': _int(row.get('Total Property Taxes and Charges')),
        }

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(v):
    """Convert numpy scalars and NaN to plain Python types for JSON serialisation."""
    if v is None:
        return None
    try:
        import math
        if math.isnan(float(v)):
            return None
    except (TypeError, ValueError):
        pass
    # Convert numpy scalar to native Python type
    return v.item() if hasattr(v, 'item') else v


def _int(v):
    """Like _val but rounds and casts to int. Returns None for missing values."""
    raw = _val(v)
    if raw is None:
        return None
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_dataset(municipalities: list[str] = MUNICIPALITIES,
                  start: int = START_YEAR,
                  end: int = END_YEAR) -> list[dict]:

    records = []

    for year in range(start, end + 1):
        print(f'Processing year {year}...')

        # Schedule 707
        try:
            data_707 = scrape_707(year, municipalities)
        except FileNotFoundError:
            print(f'  Schedule 707 not found for {year}, skipping.')
            data_707 = {}

        # Schedule 704
        try:
            data_704 = scrape_704(year, municipalities)
        except FileNotFoundError:
            print(f'  Schedule 704 not found for {year}, skipping.')
            data_704 = {}

        for muni in municipalities:
            record = {'Year': year, 'Municipality': muni}
            record.update(data_707.get(muni, {}))
            record.update(data_704.get(muni, {}))
            records.append(record)

    return records


if __name__ == '__main__':
    records = build_dataset()
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(records, f, indent=2)
    print(f'\nSaved {len(records)} records to {OUTPUT_FILE}')
