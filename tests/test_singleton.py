import threading
import time

from token_counter.singleton import SingleInstance


def test_first_instance_owns_second_bows_out():
    a = SingleInstance("dashboard")
    b = SingleInstance("dashboard")
    try:
        assert a.acquire() is True          # first owns the window
        assert b.acquire() is False         # second can't bind -> bow out
    finally:
        a.close()
        b.close()


def test_released_port_can_be_reacquired():
    a = SingleInstance("compact")
    assert a.acquire() is True
    a.close()
    b = SingleInstance("compact")
    try:
        assert b.acquire() is True          # port freed -> available again
    finally:
        b.close()


def test_second_launch_pings_focus_handler():
    owner = SingleInstance("settings")
    assert owner.acquire() is True
    fired = threading.Event()
    owner.set_focus_handler(fired.set)
    try:
        other = SingleInstance("settings")
        assert other.acquire() is False     # sends a focus ping on its way out
        assert fired.wait(2.0), "owner's focus handler should fire on a second launch"
    finally:
        owner.close()


def test_unknown_name_acts_as_sole_instance():
    s = SingleInstance("not-a-window")
    try:
        assert s.acquire() is True          # no port -> never blocks the UI
    finally:
        s.close()
