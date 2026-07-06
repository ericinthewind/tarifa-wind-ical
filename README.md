# Tarifa Wind iCal

Generate and publish an `.ics` calendar feed with the best wind windows for Tarifa, using Open-Meteo.

The calendar only creates events when your configured conditions are met.

## Features

- Automatic hourly updates with GitHub Actions.
- Public `.ics` hosting with GitHub Pages.
- No server required.
- No API key required.
- Kite, wingfoil, and windsurf profiles.
- Levante / Poniente labels.
- Session score from 0 to 100.
- Wind, gusts, direction, wave height, and wave period.

## Repository structure

```text
tarifa-wind-ical/
├── .github/
│   └── workflows/
│       └── update-ical.yml
├── public/
│   └── index.html
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── deploy.sh
└── tarifa_wind_ical.py
```

## Fast deployment from your Mac

Install GitHub CLI:

```bash
brew install gh
gh auth login
```

Then from this folder:

```bash
chmod +x deploy.sh
./deploy.sh YOUR_GITHUB_USERNAME tarifa-wind-ical
```

Example:

```bash
./deploy.sh ericmitha tarifa-wind-ical
```

After the push:

1. Open `https://github.com/YOUR_GITHUB_USERNAME/tarifa-wind-ical/settings/pages`
2. Set **Source** to **GitHub Actions**
3. Open the **Actions** tab
4. Run **Update and publish Tarifa wind iCal**

Your iCal URL will be:

```text
https://YOUR_GITHUB_USERNAME.github.io/tarifa-wind-ical/tarifa-wind.ics
```

## Add to Google Calendar

1. Open Google Calendar.
2. Click **Other calendars → + → From URL**.
3. Paste the `.ics` URL.
4. Click **Add calendar**.

Google Calendar may cache subscribed calendars, so updates might not appear instantly.

## Add to Apple Calendar

1. Open Apple Calendar.
2. Go to **File → New Calendar Subscription**.
3. Paste the `.ics` URL.
4. Choose an auto-refresh interval.

## Run locally

```bash
python3 tarifa_wind_ical.py
```

This creates:

```text
tarifa-wind.ics
```

## Profiles

Default profile is `kite`.

Run locally with another profile:

```bash
PROFILE=wingfoil python3 tarifa_wind_ical.py
PROFILE=windsurf python3 tarifa_wind_ical.py
```

In GitHub Actions, edit this line in `.github/workflows/update-ical.yml`:

```yaml
PROFILE: kite
```

Change it to:

```yaml
PROFILE: wingfoil
```

or:

```yaml
PROFILE: windsurf
```

## Main environment variables

| Variable | Default | Description |
|---|---:|---|
| `SPOT_NAME` | `Tarifa` | Calendar location/name |
| `LATITUDE` | `36.0143` | Spot latitude |
| `LONGITUDE` | `-5.6044` | Spot longitude |
| `TIMEZONE` | `Europe/Madrid` | Forecast timezone |
| `FORECAST_DAYS` | `7` | Number of forecast days |
| `PROFILE` | `kite` | `kite`, `wingfoil`, `windsurf`, or `custom` |
| `MIN_WIND_KT` | profile-based | Minimum average wind |
| `GOOD_WIND_KT` | profile-based | Good threshold |
| `EXCELLENT_WIND_KT` | profile-based | Excellent threshold |
| `MAX_GUST_KT` | profile-based | Reject sessions above this gust level |
| `MAX_WAVE_M` | profile-based | Reject sessions above this wave height |
| `MIN_BLOCK_HOURS` | `2` | Minimum consecutive usable hours |
| `WIND_SECTORS` | `60-130,240-300` | Accepted wind sectors |
| `OUTPUT_FILE` | `tarifa-wind.ics` | Output calendar filename |

To accept all wind directions:

```bash
WIND_SECTORS=0-360 python3 tarifa_wind_ical.py
```

## Data source

This project uses Open-Meteo Forecast API and Open-Meteo Marine API.
