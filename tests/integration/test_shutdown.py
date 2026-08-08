"""Graceful drain and crash recovery (§7.5): a job is either completed or
left in the DB for next-boot recovery — never silently lost."""

import asyncio
from pathlib import Path

from line_connect.storage.repository import InboxJob

from .conftest import (
    asgi_client,
    fresh_repo,
    make_settings,
    post_signed,
    running_app,
    text_event,
    webhook_payload,
)


async def test_inflight_job_finishes_within_grace(tmp_path: Path) -> None:
    calls: list[InboxJob] = []

    async def slowish_handler(job: InboxJob) -> None:
        await asyncio.sleep(0.2)
        calls.append(job)

    settings = make_settings(tmp_path, shutdown_grace_seconds=5)
    # Lifespan exits right after the POST: shutdown starts while the job runs.
    async with running_app(settings, handler=slowish_handler) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))

    assert len(calls) == 1
    async with fresh_repo(tmp_path) as repo:
        assert repo.count_by_status() == {"done": 1}


async def test_job_exceeding_grace_survives_for_recovery(tmp_path: Path) -> None:
    """Worker cancelled mid-job → row stays 'processing' → next boot re-runs it."""
    first_run_started = asyncio.Event()

    async def stuck_handler(job: InboxJob) -> None:
        first_run_started.set()
        await asyncio.sleep(30)

    settings = make_settings(tmp_path, shutdown_grace_seconds=0.2)
    async with running_app(settings, handler=stuck_handler) as app, asgi_client(app) as client:
        await post_signed(
            client, settings.webhook_path, webhook_payload(text_event())
        )
        await asyncio.wait_for(first_run_started.wait(), timeout=2)

    async with fresh_repo(tmp_path) as repo:
        assert repo.count_by_status() == {"processing": 1}, "job must not be lost"

    # Restart on the same DB: recovery re-enqueues and a working handler drains it.
    recovered_calls: list[InboxJob] = []

    async def ok_handler(job: InboxJob) -> None:
        recovered_calls.append(job)

    settings2 = make_settings(tmp_path)
    async with running_app(settings2, handler=ok_handler) as app2:
        await app2.state.pipeline.idle()
        repo2 = app2.state.repo
        assert len(recovered_calls) == 1
        assert repo2.count_by_status() == {"done": 1}


async def test_replied_job_not_rerun_after_restart(tmp_path: Path) -> None:
    """reply_sent_at set → recovery marks done instead of re-running (no double reply)."""
    settings = make_settings(tmp_path, shutdown_grace_seconds=0.2)
    stuck = asyncio.Event()

    async def handler_that_replied(job: InboxJob) -> None:
        # Simulate: reply already sent, then crash/hang before mark_done.
        await asyncio.to_thread(app.state.repo.mark_reply_sent, job.id)
        stuck.set()
        await asyncio.sleep(30)

    async with (
        running_app(settings, handler=handler_that_replied) as app,
        asgi_client(app) as client,
    ):
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await asyncio.wait_for(stuck.wait(), timeout=2)

    async with fresh_repo(tmp_path) as repo:
        assert repo.count_by_status() == {"processing": 1}

    rerun_calls: list[InboxJob] = []

    async def spy_handler(job: InboxJob) -> None:
        rerun_calls.append(job)

    async with running_app(make_settings(tmp_path), handler=spy_handler) as app2:
        await app2.state.pipeline.idle()
        assert rerun_calls == [], "already-replied job must not re-run"
        assert app2.state.repo.count_by_status() == {"done": 1}


async def test_same_chat_strict_fifo(tmp_path: Path) -> None:
    """Messages from one chat are processed in arrival order even with
    concurrent workers (shard pinning)."""
    order: list[str] = []

    async def handler(job: InboxJob) -> None:
        # Yield to tempt reordering; shard pinning must prevent it.
        await asyncio.sleep(0.01)
        order.append(job.dedup_key)

    settings = make_settings(tmp_path, worker_count=4)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        events = [
            text_event(event_id=f"evt-{i}", msg_id=f"m-{i}", text=f"msg {i}")
            for i in range(6)
        ]
        await post_signed(client, settings.webhook_path, webhook_payload(*events))
        await app.state.pipeline.idle()

    assert order == [f"evt-{i}" for i in range(6)]
