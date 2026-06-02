import pytest

from src.ui.ui_cache import ScheduleCache, ScheduleSystem


def _system(number: int) -> ScheduleSystem:
    return ScheduleSystem(number=number, text=f"Complete System #{number}\nCourse | Date | Instructor")


def test_cache_stores_systems_in_batches_of_1000_by_default():
    cache = ScheduleCache()

    cache.extend(_system(number) for number in range(1, 1002))

    assert cache.system_count == 1001
    assert cache.batch_count == 2
    assert len(cache.get_batch(0)) == 1000
    assert len(cache.get_batch(1)) == 1
    assert cache.get_batch(0)[0].number == 1
    assert cache.get_batch(1)[0].number == 1001


def test_cache_retrieves_one_based_pages():
    cache = ScheduleCache(batch_size=2)
    cache.extend([_system(1), _system(2), _system(3)])

    assert [system.number for system in cache.get_page(1)] == [1, 2]
    assert [system.number for system in cache.get_page(2)] == [3]
    assert cache.get_page(0) == []
    assert cache.get_page(3) == []


def test_cache_handles_partial_batches_and_clear():
    cache = ScheduleCache(batch_size=3)
    cache.extend([_system(1), _system(2)])

    assert cache.system_count == 2
    assert cache.batch_count == 1
    assert [system.number for system in cache.get_batch(0)] == [1, 2]

    cache.clear()

    assert cache.system_count == 0
    assert cache.batch_count == 0
    assert cache.get_batch(0) == []


def test_cache_rejects_invalid_batch_size():
    with pytest.raises(ValueError):
        ScheduleCache(batch_size=0)
