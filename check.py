import pandas as pd
import numpy as np

# Load the data
df = pd.read_excel('mlb_stats.xlsx')

# Compute relative wind direction and tailwind factors
df['RelativeAngle'] = (df['WindDirection'] - df['CompassBearing']) % 360
df['RelativeRad'] = np.deg2rad(df['RelativeAngle'])
df['TailwindFactor'] = np.cos(df['RelativeRad'])
df['WindComponent'] = df['WindSpeedMPH'] * df['TailwindFactor']

# Calculate correlations
corr_tailwind = df['TailwindFactor'].corr(df['Differential'])
corr_component = df['WindComponent'].corr(df['Differential'])

# Categorize wind orientation
def wind_category(angle):
    if angle <= 45 or angle >= 315:
        return 'Tailwind'
    elif 135 <= angle <= 225:
        return 'Headwind'
    else:
        return 'Crosswind'

df['WindCategory'] = df['RelativeAngle'].apply(wind_category)

# Aggregate statistics by category
cat_stats = df.groupby('WindCategory')['Differential'].agg(['mean', 'count']).reset_index()

# Prepare summary
summary = pd.DataFrame({
    'Metric': ['Corr(TailwindFactor, Differential)', 'Corr(WindComponent, Differential)'],
    'Value': [corr_tailwind, corr_component]
})

# Display results
print(df)
