# CampusConnect — MongoDB Edition

College Event Management System built with Flask, MongoDB, HTML, CSS and Bootstrap.

## MongoDB configuration
The app connects to the local MongoDB server using:

`mongodb://127.0.0.1:27017/`

Database: `campusconnect`

Collections:
- `events`
- `registrations`
- `counters` (internal ID counter)

The app creates the database, collections, indexes, and four sample events automatically on first successful run.

## Run on Windows (VS Code terminal)

Open the folder containing `app.py`, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

If PowerShell blocks activation, use:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Start MongoDB
Make sure MongoDB Community Server is installed and its Windows service is running.
Open Windows Services (`Win + R`, type `services.msc`), find `MongoDB Server` / `MongoDB`, and click Start if it is stopped.

## View data in MongoDB Compass
1. Open MongoDB Compass.
2. Connect to `mongodb://127.0.0.1:27017/`.
3. Open database `campusconnect`.
4. Open `events` or `registrations` collection.

## Demo admin
URL: `http://127.0.0.1:5000/admin/login`
Username: `admin`
Password: `admin123`

Change demo credentials and the secret key before any public deployment.
