# DeMark Dashboard - Deployment Guide

## Local Testing

To test the dashboard locally before deploying:

```bash
# 1. Navigate to project directory
cd y:\Liquids\Sean\30 Technical Indicators

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## Streamlit Community Cloud Deployment

### Prerequisites
- GitHub account
- Streamlit account (free tier available)

### Step 1: Push to GitHub

```bash
# Initialize git repository (if not already done)
git init
git add .
git commit -m "Initial DeMark dashboard commit"

# Add remote repository (replace YOUR_USERNAME and YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click "Create app"
4. Select your repository
5. Set the main file path to: `app.py`
6. Click "Deploy"

Streamlit will automatically install dependencies from `requirements.txt` and launch your app.

### Step 3: Share the Link

Once deployed, Streamlit provides a public URL like:
```
https://demark-dashboard.streamlit.app
```

Share this link with others!

---

## Environment Configuration

The dashboard uses `.streamlit/config.toml` for theming and behavior settings. Modify as needed.

---

## Troubleshooting

### SSL/Network Errors
- The dashboard automatically falls back to synthetic demo data if Yahoo Finance is unreachable
- This is intentional for reliability in restricted network environments
- To use live data, check your network connectivity and SSL certificates

### Import Errors
- Ensure all dependencies in `requirements.txt` are installed
- Python 3.10+ is required

### Data Issues
- Yahoo Finance data may be temporarily unavailable
- The app will display this gracefully with demo data
- Try refreshing the page after a few minutes

---

## Architecture

```
demark-dashboard/
├── app.py                          # Main Streamlit app entrypoint
├── requirements.txt                # Python dependencies
├── .streamlit/config.toml          # Streamlit configuration
├── src/demark_dashboard/
│   ├── __init__.py
│   ├── config.py                   # Asset symbols and settings
│   ├── data.py                     # Yahoo Finance data fetcher + demo data
│   ├── indicators.py               # TD Sequential implementation
│   ├── charts.py                   # Plotly interactive charts
│   └── insights.py                 # Signal interpretation engine
└── README.md                       # Project documentation
```

---

## Citation

This dashboard implements **TD Sequential** methodology as described in:
- **Perl, Jason.** *DeMark Indicators.* Bloomberg Press, 2008.

All DeMark indicator trademarks are protected by U.S. law.
