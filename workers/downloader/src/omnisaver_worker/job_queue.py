from __future__ import annotations

import json
from collections import deque
from typing import Protocol, cast

import redis

from omnisaver_downloader import Platform
from omnisaver_worker.public_job import PublicDownloadJob


class JobQueue(Protocol):
    def enqueue(self, job: PublicDownloadJob) -> None:
        pass

    def dequeue(self) -> PublicDownloadJob | None:
        pass


class RedisClient(Protocol):
    def lpush(self, name: str, value: str) -> object:
        pass

    def rpop(self, name: str) -> bytes | str | None:
        pass


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.jobs: deque[PublicDownloadJob] = deque()

    def enqueue(self, job: PublicDownloadJob) -> None:
        self.jobs.append(job)

    def dequeue(self) -> PublicDownloadJob | None:
        if not self.jobs:
            return None
        return self.jobs.popleft()


class RedisJobQueue:
    def __init__(
        self,
        redis_client: RedisClient,
        *,
        queue_name: str = "omnisaver:download_jobs",
    ) -> None:
        self.redis = redis_client
        self.queue_name = queue_name

    def enqueue(self, job: PublicDownloadJob) -> None:
        self.redis.lpush(self.queue_name, _job_to_json(job))

    def dequeue(self) -> PublicDownloadJob | None:
        payload = self.redis.rpop(self.queue_name)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return _job_from_json(payload)


def build_redis_job_queue(
    redis_url: str,
    *,
    queue_name: str = "omnisaver:download_jobs",
) -> RedisJobQueue:
    client = cast(RedisClient, redis.Redis.from_url(redis_url))
    return RedisJobQueue(client, queue_name=queue_name)


def _job_to_json(job: PublicDownloadJob) -> str:
    return json.dumps(
        {
            "job_id": job.job_id,
            "telegram_user_id": job.telegram_user_id,
            "chat_id": job.chat_id,
            "platform": job.platform.value,
            "url": job.url,
        },
        sort_keys=True,
    )


def _job_from_json(payload: str) -> PublicDownloadJob:
    data = json.loads(payload)
    return PublicDownloadJob(
        job_id=str(data["job_id"]),
        telegram_user_id=int(data["telegram_user_id"]),
        chat_id=int(data["chat_id"]),
        platform=Platform(str(data["platform"])),
        url=str(data["url"]),
    )
