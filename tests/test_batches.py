from shipment_tracker.batches import make_batches, numbers_to_check
from shipment_tracker.sheets.memory_sheet import MemorySheet


def test_picks_numbers_that_still_need_checking():
    sheet = MemorySheet(
        {
            "A": [
                ["Tracking", "Status"],
                ["111111111111", "In transit, ETA 10/19"],
                ["222222222222", "Delivered 10/14"],  # done: skip
                ["1111 1111 1111", ""],  # duplicate of the first, differently typed
                ["1.00000E+11", ""],  # unusable: skip
                ["", ""],  # blank: skip
            ],
            "B": [["Tracking"], ["333333333333"]],
        }
    )
    assert numbers_to_check(sheet, ["A", "B"]) == ["111111111111", "333333333333"]


def test_batches_hold_at_most_30():
    numbers = [str(100000000000 + i) for i in range(47)]
    batches = make_batches(numbers)
    assert [len(b) for b in batches] == [30, 17]
    assert sum(batches, []) == numbers


def test_no_numbers_means_no_batches():
    assert make_batches([]) == []
