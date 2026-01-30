# 🎬 Django & TMDb Autocomplete Integration Course
## A Beginner's Guide to Extending the Django Admin

Welcome! This guide explains how we built the "Add Film" autocomplete feature in your Django project. We will cover the core concepts of Django, how external APIs work, and how to connect it all with JavaScript.

---

## 1. The Context: Why are we doing this?

**The Problem:**
Imagine you run a cinema. Manually typing in every movie detail (Title, Release Date, Poster URL, Synopsis, Cast, etc.) is tedious and error-prone.

**The Solution:**
We use **TMDb (The Movie Database)**, a huge online database of movies (like Wikipedia for films).
Instead of typing, we want to:
1.  **Type the title** in our Admin panel.
2.  **See suggestions** from TMDb automatically.
3.  **Click one button** to import all the data instantly.

---

## 2. The Architecture: How the pieces fit together

To make this work, we need three layers communicating with each other:

1.  **The External Layer (TMDb)**: The source of truth. We need an API Key to ask it questions.
2.  **The Backend (Django)**: Our Python server. It acts as a middleman. It talks to TMDb, cleans the data, and saves it to our Database.
3.  **The Frontend (Browser/Admin)**: The interface you see. It listens to your keystrokes and asks the Backend for help.

```
[ Browser / JS ]  <--->  [ Django Views ]  <--->  [ TMDb API ]
      |                         |
(User types "Inception")   (Fetches Data)
      |                         |
(Displays Dropdown)    (Saves to SQLite DB)
```

---

## 3. Step-by-Step Implementation

### Step 1: The Service Layer (`providers/tmdb.py`)
**"The Messenger"**

Before we build any web pages, we need Python functions to talk to TMDb. We created a "Service".
*   **What it does:** It sends HTTP requests (like a browser does) to `api.themoviedb.org`.
*   **Key Functions:**
    *   `search_movies(query)`: Takes a string (e.g., "Matrix") and returns a list of results.
    *   `fetch_movie_details(id)`: Takes a specific ID and gets the full info (cast, synopsis, image).

### Step 2: The API Views (`tmdb_views.py`)
**"The Doorway"**

Our JavaScript in the browser cannot call Python functions directly. It needs a URL to hit. We created **API endpoints**.
*   **Search Endpoint (`/api/tmdb/search/`)**:
    *   Receives `?q=Matrix` from the browser.
    *   Calls the service `search_movies("Matrix")`.
    *   Returns the data as **JSON** (JavaScript Object Notation), which the browser understands.
    *   *Analogy:* It's like a waiter taking your order to the kitchen.
*   **Import Endpoint (`/api/tmdb/import/`)**:
    *   Receives a POST request with a `tmdb_id`.
    *   Fetches details, saves the `Film`, `Genre`, and `Cast` to the database.
    *   Returns `{ "ok": true, "film_id": 12 }`.

### Step 3: The Admin Customization (`change_form.html`)
**"The Interface"**

Django's Admin is powerful because you can override its templates.
We modified `cinema/templates/film/change_form.html`.
*   **`{% extends "admin/change_form.html" %}`**: This tells Django "Use the standard admin page, but let me add some stuff."
*   **The JavaScript Injection**: We wrote a script that runs when the page loads.

### Step 4: The JavaScript Logic
**"The Brains of the Operation"**

References in `change_form.html`. Here is the logic flow:
1.  **Event Listener**: The code watches the `Title` input field.
    *   `titleInput.addEventListener("input", ...)`
2.  **Debouncing**:
    *   We don't want to search on every letter (T... Th... The...). That would spam the API.
    *   We wait 400ms after you *stop* typing before sending the request.
3.  **Fetching Data**:
    *   `fetch('/api/tmdb/search/?q=' + query)`
4.  **Building the UI**:
    *   We create a `<div>` (dropdown) on the fly.
    *   We loop through the JSON results and create HTML "cards" for each movie.
5.  **Handling the Click**:
    *   When you click "Importer", it sends a POST request to our Import Endpoint.
    *   Upon success, it redirects you: `window.location.href = '../' + new_id + '/change/'`.

---

## 4. Key Takeaways for Beginners

1.  **Don't reinvent the wheel:** Django Admin gives you a CRUD (Create, Read, Update, Delete) interface for free. We just "sprinkled" some magic on top.
2.  **Separation of Concerns:**
    *   **Logic** stays in Python (Views/Services).
    *   **Interactivity** stays in JavaScript (Templates).
    *   They communicate *only* via JSON.
3.  **AJAX (Asynchronous JavaScript and XML):** This is the technique of fetching data (searching movies) without reloading the entire page.

## 5. Summary Code Flow

1.  **User** types "Titan" in Admin Title.
2.  **JS** waits 400ms -> GET `/api/tmdb/search/?q=Titan`.
3.  **Django** calls `tmdb.search_movies("Titan")` -> returns list.
4.  **JS** draws the list under the input box.
5.  **User** clicks "Titan A.E.".
6.  **JS** POSTs (tmdb_id=7450) to `/api/tmdb/import/`.
7.  **Django** fetches details, **Saves to DB**, returns ID.
8.  **JS** redirects browser to the Edit page for the new movie.

---
*Generated by Antigravity for the Cinema Project*
