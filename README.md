# Tarifa Wind iCal

Generate and publish an automatically updated `.ics` calendar feed with the best wind windows for Tarifa, using Open-Meteo.

The feed creates calendar events only when your conditions are met, instead of filling your calendar with every forecast hour.

## Features

- Uses Open-Meteo Forecast API for wind speed, gusts, and direction.
- Uses Open-Meteo Marine API for wave height, period, and direction.
- Publishes automatically to GitHub Pages.
- Updates every hour via GitHub Actions.
- No API key required for typical non-commercial use.
- No third-party Python packages required.
- Includes profiles for `kite`, `wingfoil`, and `windsurf`.
- Adds a session score from `0` to `100`.
- Labels Tarifa wind as Levante or Poniente when applicable.

refresh immediately after each hourly update.
