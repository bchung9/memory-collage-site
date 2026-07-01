# Memoria

A Pinterest-style memory keeper — share photos and short videos with captions,
date, and location, browse a masonry feed, like things, and keep a personal
profile of everything you've saved.

## Setup

```bash
cd memoria
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 — create an account and start uploading.

## What's included

- Username/password accounts (passwords hashed, sessions via Flask)
- Upload photos (jpg/png/gif/webp) or short videos (mp4/webm/mov), up to 50MB
- Pinterest-style masonry feed of every memory, newest first
- Caption search
- Like button
- Per-user profile page with their own grid
- Delete your own memories

## Notes / next steps you might want

- This uses Flask's built-in dev server — for real deployment, run behind
  gunicorn/uwsgi + nginx.
- SECRET_KEY in app.py is a placeholder — change it before deploying anywhere
  public.
- Storage is local disk (`static/uploads/`) + SQLite (`instance/memoria.db`).
  For scale you'd want S3 (or similar) + Postgres.
- Ideas for "next basic feature": comments, follow/following, collections/boards
  (the Pinterest "board" concept), private vs public memories.
