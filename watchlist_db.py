from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).parent / "watchlist.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    min_percent REAL NOT NULL DEFAULT 5.0,
    PRIMARY KEY (user_id, asset_id)
);
"""


@dataclass
class WatchEntry:
    user_id: int
    asset_id: int
    item_name: str
    min_percent: float


class WatchlistDB:
    def __init__(self, path: Path = DB_PATH):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        self._lock = asyncio.Lock()

    async def add(self, user_id: int, asset_id: int, item_name: str, min_percent: float) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT INTO watchlist (user_id, asset_id, item_name, min_percent) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, asset_id) DO UPDATE SET min_percent = excluded.min_percent",
                (user_id, asset_id, item_name, min_percent),
            )
            await asyncio.to_thread(self._conn.commit)

    async def remove(self, user_id: int, asset_id: int) -> bool:
        async with self._lock:
            cursor = await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM watchlist WHERE user_id = ? AND asset_id = ?",
                (user_id, asset_id),
            )
            await asyncio.to_thread(self._conn.commit)
            return cursor.rowcount > 0

    async def list_for_user(self, user_id: int) -> list[WatchEntry]:
        async with self._lock:
            rows = await asyncio.to_thread(
                self._conn.execute,
                "SELECT user_id, asset_id, item_name, min_percent FROM watchlist WHERE user_id = ? "
                "ORDER BY item_name",
                (user_id,),
            )
            return [WatchEntry(*row) for row in rows.fetchall()]

    async def watchers_for_asset(self, asset_id: int) -> list[WatchEntry]:
        async with self._lock:
            rows = await asyncio.to_thread(
                self._conn.execute,
                "SELECT user_id, asset_id, item_name, min_percent FROM watchlist WHERE asset_id = ?",
                (asset_id,),
            )
            return [WatchEntry(*row) for row in rows.fetchall()]

    async def all_watched_asset_ids(self) -> set[int]:
        async with self._lock:
            rows = await asyncio.to_thread(
                self._conn.execute, "SELECT DISTINCT asset_id FROM watchlist"
            )
            return {row[0] for row in rows.fetchall()}
