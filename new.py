#!/usr/bin/env python3
import pandas as pd
from stadiums_store import stadium_data

# build lookup by StadiumID
stadium_lookup = {s['StadiumID']: s for s in stadium_data}

def get_attr(stadium_id, attr):
    entry = stadium_lookup.get(stadium_id)
    return entry.get(attr) if entry else None

def main():
    input_file  = 'stats_plus_odds.xlsx'
    output_file = 'stats_v2.xlsx'

    # ─── load sheets ───────────────────────────────
    xls        = pd.ExcelFile(input_file)
    df_main    = pd.read_excel(xls, 'Main')
    df_extras0 = pd.read_excel(xls, 'Extras')

    # ─── enrich Main with new cols ────────────────
    for col in ('StadiumName','Latitude','Longitude','CompassBearing','OutdoorOnly'):
        df_main[col] = df_main['StadiumID'].apply(lambda sid: get_attr(sid, col))

    # ─── define masks ─────────────────────────────
    has_latlon    = df_main['Latitude'].notnull() & df_main['Longitude'].notnull()
    is_outdoor    = df_main['OutdoorOnly'] == 'Yes'
    is_indoor_ok  = (df_main['OutdoorOnly'] == 'No') & has_latlon

    # ─── split into three DataFrames ──────────────
    df_main_clean    = df_main[ is_outdoor    & has_latlon  ].copy()
    df_indoor        = df_main[ is_indoor_ok               ].copy()
    df_extras_move   = df_main[ ~(is_outdoor & has_latlon) & ~is_indoor_ok ].copy()

    # ─── enrich original Extras sheet ─────────────
    for col in ('StadiumName','Latitude','Longitude','CompassBearing','OutdoorOnly'):
        df_extras0[col] = df_extras0['StadiumID'].apply(lambda sid: get_attr(sid, col))
    df_extras = pd.concat([df_extras0, df_extras_move], ignore_index=True)

    # ─── write out to stats_v2.xlsx ───────────────
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_main_clean.to_excel(writer, sheet_name='Main',         index=False)
        df_indoor.to_excel(writer,     sheet_name='IndoorExtras', index=False)
        df_extras.to_excel(writer,     sheet_name='Extras',       index=False)

if __name__ == '__main__':
    main()
