import threading
import unittest
from collections import OrderedDict

from app.bot import FeishuBot


class CoordinatedRecentMessages:
    def __init__(self) -> None:
        self._data: "OrderedDict[str, float]" = OrderedDict()
        self._contains_calls = 0
        self._second_entered = threading.Event()

    def items(self):
        return self._data.items()

    def popitem(self, last: bool = True):
        return self._data.popitem(last=last)

    def __bool__(self) -> bool:
        return bool(self._data)

    def __contains__(self, key: str) -> bool:
        self._contains_calls += 1
        if self._contains_calls == 1:
            self._second_entered.wait(timeout=0.2)
        else:
            self._second_entered.set()
        return key in self._data

    def __setitem__(self, key: str, value: float) -> None:
        self._data[key] = value


class FeishuBotDeduplicationTests(unittest.TestCase):
    def test_should_process_message_is_thread_safe(self) -> None:
        bot = FeishuBot.__new__(FeishuBot)
        bot._recent_message_ids = CoordinatedRecentMessages()
        bot._recent_message_ids_lock = threading.Lock()

        results = []
        start = threading.Event()

        def worker() -> None:
            start.wait()
            results.append(bot._should_process_message("same-message-id"))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()

        start.set()

        for thread in threads:
            thread.join()

        self.assertEqual(sum(results), 1)


if __name__ == "__main__":
    unittest.main()
