import sqlite3
import csv
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.ensure_db()

    def ensure_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT
                )
                """
            )

    def add_log(self, task_name: str, status: str, details: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO logs (timestamp, task_name, status, details) VALUES (?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_name, status, details),
            )

    def clear_logs(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM logs")

    def export_to_csv(self, save_path: str) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT timestamp, task_name, status, details FROM logs ORDER BY id DESC")
        rows = cur.fetchall()
        with open(save_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "task_name", "status", "details"])
            writer.writerows(rows)

    def get_logs(self, date_filter: str, status_filter: str, search_text: str, limit: int = 200) -> tuple:
        conditions = []
        params = []

        if date_filter and date_filter != "Tümü":
            now = datetime.now()
            if date_filter == "Bugün":
                cutoff_date = now.strftime("%Y-%m-%d 00:00:00")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)
            elif date_filter == "Son 7 Gün":
                cutoff_date = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)
            elif date_filter == "Son 30 Gün":
                cutoff_date = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                conditions.append("timestamp >= ?")
                params.append(cutoff_date)

        if status_filter and status_filter != "Tümü":
            conditions.append("status = ?")
            params.append(status_filter)

        if search_text:
            conditions.append("(LOWER(task_name) LIKE ? OR LOWER(details) LIKE ?)")
            term = f"%{search_text}%"
            params.extend([term, term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cur = self.conn.cursor()
        cur.execute(f"SELECT timestamp, task_name, status, details FROM logs {where_clause} ORDER BY id DESC LIMIT ?", params + [limit])
        rows = cur.fetchall()

        cur.execute(f"SELECT status, COUNT(*) FROM logs {where_clause} GROUP BY status", params)
        status_counts = dict(cur.fetchall())

        return rows, status_counts

    def close(self) -> None:
        self.conn.close()