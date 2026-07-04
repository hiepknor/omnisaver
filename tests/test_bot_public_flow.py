from omnisaver_bot import (
    create_public_download_job_from_message,
    enqueue_public_download_job_from_message,
)
from omnisaver_downloader import Platform, UnsupportedUrlError
from omnisaver_worker import InMemoryJobQueue


def test_create_public_download_job_from_message_uses_first_supported_url() -> None:
    job = create_public_download_job_from_message(
        message="first https://pin.it/abc second https://x.com/user/status/1",
        telegram_user_id=123,
        chat_id=456,
    )

    assert job.telegram_user_id == 123
    assert job.chat_id == 456
    assert job.platform is Platform.PINTEREST
    assert job.url == "https://pin.it/abc"
    assert job.job_id


def test_create_public_download_job_from_message_rejects_missing_url() -> None:
    try:
        create_public_download_job_from_message(
            message="no url here",
            telegram_user_id=123,
            chat_id=456,
        )
    except UnsupportedUrlError as exc:
        assert exc.code == "UNSUPPORTED_URL"
        assert exc.safe_message == "Vui lòng gửi một link media được hỗ trợ."
    else:
        raise AssertionError("expected UnsupportedUrlError")


def test_enqueue_public_download_job_from_message_enqueues_without_downloading() -> None:
    queue = InMemoryJobQueue()

    job = enqueue_public_download_job_from_message(
        queue=queue,
        message="save https://youtube.com/watch?v=abc",
        telegram_user_id=123,
        chat_id=456,
    )

    assert queue.dequeue() == job
    assert job.platform is Platform.YOUTUBE
