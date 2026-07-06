import time
import unittest

from telugu_ai_news_analyzer import APIKeyManager


class APIKeyManagerTests(unittest.TestCase):
    def test_round_robin_cycles_across_available_keys(self):
        manager = APIKeyManager(["k1", "k2", "k3"], cooldown_seconds=5.0)

        first = manager.acquire()
        manager.mark_success(first.index, latency_seconds=0.1, tokens=100)

        second = manager.acquire()
        manager.mark_success(second.index, latency_seconds=0.2, tokens=100)

        third = manager.acquire()
        manager.mark_success(third.index, latency_seconds=0.3, tokens=100)

        fourth = manager.acquire()
        manager.mark_success(fourth.index, latency_seconds=0.4, tokens=100)

        self.assertEqual([first.index, second.index, third.index, fourth.index], [1, 2, 3, 1])

    def test_rate_limit_cools_the_key_and_switches_immediately(self):
        manager = APIKeyManager(["k1", "k2"], cooldown_seconds=5.0)

        first = manager.acquire()
        manager.mark_failure(first.index, "429 rate limit reached", latency_seconds=0.4)

        second = manager.acquire()
        self.assertEqual(second.index, 2)
        self.assertGreaterEqual(manager._keys[0].available_at, time.monotonic())

    def test_validation_failure_does_not_cool_the_key(self):
        manager = APIKeyManager(["k1"], cooldown_seconds=5.0)

        first = manager.acquire()
        manager.mark_failure(first.index, "Summary too short", latency_seconds=0.2)

        next_key = manager.acquire()
        self.assertEqual(next_key.index, 1)
        self.assertLessEqual(manager._keys[0].available_at, time.monotonic())


if __name__ == "__main__":
    unittest.main()
