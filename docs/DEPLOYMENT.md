# Deployment: Streamlit Community Cloud

The app is a conventional Streamlit app with no secrets, no database server and no external API calls,
so Streamlit Community Cloud is the simplest host. (Vercel is not a fit for a long-running Streamlit
server; using it would mean a separate Next.js front end plus a separately hosted Python API.)

## What the repository already provides

| Item | Value |
|---|---|
| Entrypoint (main file path) | `app.py` |
| Dependencies | `requirements.txt` (runtime only; dev tools are in `requirements-dev.txt`) |
| Theme / server config | `.streamlit/config.toml` (no secrets) |
| Data | `data/sample/synthetic_pricing_data.csv` (synthetic, committed) |
| Secrets | None required. `.streamlit/secrets.toml` is git-ignored. |

## Steps (done in your browser)

1. Push the repository to GitHub.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app** → **Deploy a public app from GitHub** (or "Yup, I have an app").
4. Choose the repository, branch `main`, and main file path `app.py`.
5. Open **Advanced settings** and choose **Python 3.12**. Leave secrets empty.
6. Pick a custom subdomain if you want one, then click **Deploy**.
7. The first build takes a few minutes while dependencies install. When the app loads, check every page.

## Verifying the live app

- The Executive Overview loads and the sidebar shows the synthetic-data notice.
- Each page renders without a red error box.
- The Data Quality page accepts `data/sample/messy_import_example.csv` and shows the validation log.
- `https://<your-app>.streamlit.app/_stcore/health` returns `ok`.

## Notes

- Community Cloud apps sleep after a period without traffic; the first visit afterwards wakes them up.
- Uploaded CSVs are processed in memory for the visitor's session and are not stored, but a public app is
  public: do not upload confidential data to it.
- To update the app, push to the deployed branch; Community Cloud redeploys automatically.
