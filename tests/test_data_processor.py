from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import data_processor as dp


class DataProcessorTests(unittest.TestCase):
    def test_save_history_ignores_duplicate_play(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            tracks = [
                {
                    "played_at": "2026-05-01T14:30:00Z",
                    "id": "track-1",
                    "name": "Clean Data",
                    "artist_name": "Jordan Avery",
                    "album_name": "Portfolio Sessions",
                    "duration_ms": 180000,
                    "popularity": 42,
                },
                {
                    "played_at": "2026-05-01T14:30:00Z",
                    "id": "track-1",
                    "name": "Clean Data",
                    "artist_name": "Jordan Avery",
                    "album_name": "Portfolio Sessions",
                    "duration_ms": 180000,
                    "popularity": 42,
                },
            ]

            inserted = dp.save_listening_history(db_path, tracks)
            history = dp.get_listening_history(db_path)

            self.assertEqual(inserted, 1)
            self.assertEqual(len(history), 1)

    def test_stats_return_zero_state_for_empty_database(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "history.db"
            stats = dp.get_listening_stats(db_path, date(2026, 5, 1), date(2026, 5, 31))

            self.assertEqual(stats["minutes"], 0)
            self.assertEqual(stats["top_artist"], "No data yet")

    def test_duplicate_playlist_detection(self) -> None:
        duplicates = dp.find_duplicate_tracks(
            {
                "Focus": [{"id": "track-1", "name": "Repeat", "artist_name": "Analyst"}],
                "Workout": [{"id": "track-1", "name": "Repeat", "artist_name": "Analyst"}],
            }
        )

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates.iloc[0]["track_name"], "Repeat")


if __name__ == "__main__":
    unittest.main()
