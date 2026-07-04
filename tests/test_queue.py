from omnisaver_downloader import Platform
from omnisaver_worker import InMemoryJobQueue, PublicDownloadJob, RedisJobQueue


def test_in_memory_queue_round_trips_jobs_fifo() -> None:
    queue = InMemoryJobQueue()
    first = PublicDownloadJob(
        job_id="00000000-0000-0000-0000-000000000001",
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.YOUTUBE,
        url="https://youtube.com/watch?v=abc",
    )
    second = PublicDownloadJob(
        job_id="00000000-0000-0000-0000-000000000002",
        telegram_user_id=101,
        chat_id=201,
        platform=Platform.GENERIC,
        url="https://example.com/video.mp4",
    )

    queue.enqueue(first)
    queue.enqueue(second)

    assert queue.dequeue() == first
    assert queue.dequeue() == second
    assert queue.dequeue() is None


def test_redis_queue_serializes_jobs_fifo() -> None:
    redis = FakeRedis()
    queue = RedisJobQueue(redis)
    job = PublicDownloadJob(
        job_id="00000000-0000-0000-0000-000000000001",
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.YOUTUBE,
        url="https://youtube.com/watch?v=abc",
    )

    queue.enqueue(job)

    assert redis.names == ["omnisaver:download_jobs"]
    assert queue.dequeue() == job
    assert queue.dequeue() is None


class FakeRedis:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.names: list[str] = []

    def lpush(self, name: str, value: str) -> int:
        self.names.append(name)
        self.values.insert(0, value)
        return len(self.values)

    def rpop(self, name: str) -> str | None:
        self.names.append(name)
        if not self.values:
            return None
        return self.values.pop()
