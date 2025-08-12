import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import altair as alt

# ---------------- Database helpers ----------------
DB_PATH = "library.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            genre TEXT,
            year INTEGER,
            total_copies INTEGER DEFAULT 1,
            available INTEGER DEFAULT 1,
            added_on TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            action TEXT,
            user TEXT,
            timestamp TEXT,
            FOREIGN KEY(book_id) REFERENCES books(id)
        )
    ''')
    conn.commit()
    conn.close()


def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    data = None
    if fetch:
        data = c.fetchall()
    conn.commit()
    conn.close()
    return data

# ---------------- CRUD operations ----------------

def add_book(title, author, genre, year, copies):
    now = datetime.now().isoformat()
    run_query(
        "INSERT INTO books (title, author, genre, year, total_copies, available, added_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, author, genre, year, copies, copies, now)
    )


def list_books():
    rows = run_query("SELECT * FROM books ORDER BY id", fetch=True)
    cols = ["id","title","author","genre","year","total_copies","available","added_on"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def search_books(q):
    q_like = f"%{q}%"
    rows = run_query(
        "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR genre LIKE ? ORDER BY title",
        (q_like, q_like, q_like),
        fetch=True
    )
    cols = ["id","title","author","genre","year","total_copies","available","added_on"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def borrow_book(book_id, user_name):
    # check availability
    book = run_query("SELECT available FROM books WHERE id = ?", (book_id,), fetch=True)
    if not book:
        return False, "Book not found"
    if book[0][0] <= 0:
        return False, "No copies available"
    run_query("UPDATE books SET available = available - 1 WHERE id = ?", (book_id,))
    run_query("INSERT INTO transactions (book_id, action, user, timestamp) VALUES (?, 'borrow', ?, ?)",
             (book_id, user_name, datetime.now().isoformat()))
    return True, "Borrowed successfully"


def return_book(book_id, user_name):
    # increase availability but not exceeding total_copies
    row = run_query("SELECT available, total_copies FROM books WHERE id = ?", (book_id,), fetch=True)
    if not row:
        return False, "Book not found"
    available, total = row[0]
    if available >= total:
        return False, "All copies already in library"
    run_query("UPDATE books SET available = available + 1 WHERE id = ?", (book_id,))
    run_query("INSERT INTO transactions (book_id, action, user, timestamp) VALUES (?, 'return', ?, ?)",
             (book_id, user_name, datetime.now().isoformat()))
    return True, "Returned successfully"


def get_transactions(limit=200):
    rows = run_query("SELECT t.id, t.book_id, b.title, t.action, t.user, t.timestamp FROM transactions t LEFT JOIN books b ON t.book_id = b.id ORDER BY t.timestamp DESC LIMIT ?",
                     (limit,), fetch=True)
    cols = ["id","book_id","title","action","user","timestamp"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)

# ---------------- Sample data loader ----------------

def load_sample_data():
    sample_books = [
        ("The Great Gatsby", "F. Scott Fitzgerald", "Fiction", 1925, 3),
        ("A Brief History of Time", "Stephen Hawking", "Science", 1988, 2),
        ("The Pragmatic Programmer", "Andrew Hunt", "Technology", 1999, 1),
        ("To Kill a Mockingbird", "Harper Lee", "Fiction", 1960, 2),
        ("Deep Work", "Cal Newport", "Productivity", 2016, 1),
    ]
    for t,a,g,y,c in sample_books:
        add_book(t,a,g,y,c)

# ---------------- Streamlit UI ----------------

st.set_page_config(page_title="Library Management — Streamlit", layout="wide")
init_db()

st.title("📚 Library Management System (Streamlit)")

menu = st.sidebar.selectbox("Go to", ["Dashboard", "Manage Books", "Borrow/Return", "Transactions", "Load Sample Data", "About"])

if menu == "Dashboard":
    st.header("Library Dashboard")
    df = list_books()
    col1, col2 = st.columns([2,1])
    with col1:
        st.subheader("Book Catalog")
        st.dataframe(df)

    with col2:
        st.subheader("Quick Stats")
        total_books = df['total_copies'].sum() if not df.empty else 0
        unique_titles = len(df) if not df.empty else 0
        available = df['available'].sum() if not df.empty else 0
        st.metric("Total copies", total_books)
        st.metric("Unique titles", unique_titles)
        st.metric("Available copies", available)

        st.subheader("Most common genres")
        if not df.empty:
            genre_counts = df.groupby('genre')['total_copies'].sum().reset_index()
            chart = alt.Chart(genre_counts).mark_bar().encode(x='genre', y='total_copies')
            st.altair_chart(chart, use_container_width=True)
        else:
            st.write("No books yet")

    st.subheader("Borrow / Return activity (recent)")
    tx = get_transactions(50)
    st.dataframe(tx)

elif menu == "Manage Books":
    st.header("Add a new book")
    with st.form(key='add_book'):
        t = st.text_input("Title")
        a = st.text_input("Author")
        g = st.text_input("Genre")
        y = st.number_input("Year", min_value=1000, max_value=2100, value=2020)
        c = st.number_input("Number of copies", min_value=1, max_value=100, value=1)
        submitted = st.form_submit_button("Add Book")
        if submitted:
            if t.strip() == "":
                st.error("Title is required")
            else:
                add_book(t.strip(), a.strip(), g.strip(), int(y), int(c))
                st.success(f"Added '{t}'")

    st.markdown("---")
    st.header("Search / Edit books")
    q = st.text_input("Search by title/author/genre")
    if q:
        res = search_books(q)
        st.dataframe(res)
    else:
        st.write("Type in the search box to filter books")

elif menu == "Borrow/Return":
    st.header("Borrow or Return a Book")
    df = list_books()
    if df.empty:
        st.info("No books available. Add some in Manage Books.")
    else:
        book_choice = st.selectbox("Choose book (id - title)", df.apply(lambda r: f"{r['id']} - {r['title']} ({r['available']} available)", axis=1).tolist())
        book_id = int(book_choice.split(" - ")[0])
        user_name = st.text_input("Your name")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Borrow"):
                if user_name.strip() == "":
                    st.error("Please enter your name")
                else:
                    ok, msg = borrow_book(book_id, user_name.strip())
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
        with col2:
            if st.button("Return"):
                if user_name.strip() == "":
                    st.error("Please enter your name")
                else:
                    ok, msg = return_book(book_id, user_name.strip())
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

elif menu == "Transactions":
    st.header("Transactions")
    tx = get_transactions(500)
    st.dataframe(tx)

elif menu == "Load Sample Data":
    st.warning("This will add sample books to the DB. Do not click if you already have production data")
    if st.button("Load Sample Books"):
        load_sample_data()
        st.success("Sample data loaded. Go to Dashboard to view")

elif menu == "About":
    st.header("About this app")
    st.markdown(
        """
        **Streamlit Library Management System**

        Features:
        - Add, search and list books (stored in a local SQLite DB)
        - Borrow and return workflow with transaction logging
        - Dashboard with simple charts showing genres and recent activity
        - Single-file demo app that you can extend (user auth, reservations, fines, import/export, cloud DB, etc.)

        Suggested extensions for the lab:
        - Add user accounts & authentication
        - Allow CSV import/export for bulk book updates
        - Add due dates and automatic fine calculation
        - Role-based views (librarian vs student)
        - Deploy to Streamlit Cloud or a VM and use PostgreSQL for persistence
        """
    )

# ---------------- End ----------------

