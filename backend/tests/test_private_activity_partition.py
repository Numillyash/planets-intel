from app.services.private_sync import _partition_private_activity_by_game


def test_private_activity_is_partitioned_only_by_positive_raw_game_id():
    records = [
        {"id": 1, "gameid": 100, "message": "a"},
        {"id": 2, "gameid": 200, "message": "b"},
        {"id": 3, "gameid": 100, "message": "c"},
        {"id": 4, "gameid": 0, "message": "invalid"},
        {"id": 5, "message": "missing"},
        {"id": 6, "gameid": True, "message": "bool is not an id"},
    ]

    grouped = _partition_private_activity_by_game(records)

    assert list(grouped) == [100, 200]
    assert [item["id"] for item in grouped[100]] == [1, 3]
    assert [item["id"] for item in grouped[200]] == [2]
