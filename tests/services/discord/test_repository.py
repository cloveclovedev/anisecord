from unittest.mock import AsyncMock, MagicMock

import discord

from bot.services.discord.repository import DiscordRepository


def make_repo() -> DiscordRepository:
    return DiscordRepository()


def make_thread(name: str, archived: bool = False) -> MagicMock:
    thread = MagicMock(spec=discord.Thread)
    thread.name = name
    thread.archived = archived
    thread.edit = AsyncMock()
    thread.send = AsyncMock()
    thread.history = MagicMock()
    return thread


def make_channel(active_threads: list | None = None) -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.threads = active_threads or []
    channel.create_thread = AsyncMock()
    channel.archived_threads = MagicMock()
    return channel


async def async_iter(items):
    for item in items:
        yield item


class TestFindOrCreateThread:
    async def test_returns_existing_active_thread(self):
        repo = make_repo()
        existing = make_thread("2026-02-20 日報")
        channel = make_channel(active_threads=[existing])

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")

        assert result is existing
        channel.create_thread.assert_not_called()

    async def test_creates_new_thread_when_not_found(self):
        repo = make_repo()
        channel = make_channel(active_threads=[])

        # No archived threads
        channel.archived_threads.return_value = async_iter([])

        new_thread = make_thread("2026-02-20 日報")
        channel.create_thread.return_value = new_thread

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")

        assert result is new_thread
        channel.create_thread.assert_called_once_with(
            name="2026-02-20 日報",
            type=discord.ChannelType.public_thread,
        )

    async def test_finds_archived_thread_and_unarchives(self):
        repo = make_repo()
        archived_thread = make_thread("2026-02-20 日報", archived=True)
        channel = make_channel(active_threads=[])

        channel.archived_threads.return_value = async_iter([archived_thread])

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")

        assert result is archived_thread
        archived_thread.edit.assert_called_once_with(archived=False)
        channel.create_thread.assert_not_called()

    async def test_skips_archived_thread_with_different_name(self):
        repo = make_repo()
        other_thread = make_thread("2026-02-19 日報", archived=True)
        channel = make_channel(active_threads=[])

        channel.archived_threads.return_value = async_iter([other_thread])

        new_thread = make_thread("2026-02-20 日報")
        channel.create_thread.return_value = new_thread

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")

        assert result is new_thread
        channel.create_thread.assert_called_once()

    async def test_handles_archived_threads_exception(self):
        repo = make_repo()
        channel = make_channel(active_threads=[])

        channel.archived_threads.side_effect = Exception("API error")

        new_thread = make_thread("2026-02-20 日報")
        channel.create_thread.return_value = new_thread

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")

        assert result is new_thread
        channel.create_thread.assert_called_once()


class TestFetchThreadMessages:
    async def test_returns_message_contents_as_strings(self):
        repo = make_repo()
        thread = make_thread("2026-02-20 日報")

        msg1 = MagicMock()
        msg1.content = "Hello"
        msg2 = MagicMock()
        msg2.content = "World"

        thread.history.return_value = async_iter([msg1, msg2])

        result = await repo.fetch_thread_messages(thread)

        assert result == ["Hello", "World"]
        thread.history.assert_called_once_with(limit=100, oldest_first=True)

    async def test_respects_custom_limit(self):
        repo = make_repo()
        thread = make_thread("test")

        thread.history.return_value = async_iter([])

        await repo.fetch_thread_messages(thread, limit=50)

        thread.history.assert_called_once_with(limit=50, oldest_first=True)

    async def test_returns_empty_list_for_empty_thread(self):
        repo = make_repo()
        thread = make_thread("empty thread")

        thread.history.return_value = async_iter([])

        result = await repo.fetch_thread_messages(thread)

        assert result == []


class TestSendToThread:
    async def test_sends_short_message_directly(self):
        repo = make_repo()
        thread = make_thread("test")

        await repo.send_to_thread(thread, "Hello!")

        thread.send.assert_called_once_with("Hello!")

    async def test_sends_exactly_2000_chars_without_splitting(self):
        repo = make_repo()
        thread = make_thread("test")
        content = "x" * 2000

        await repo.send_to_thread(thread, content)

        thread.send.assert_called_once_with(content)

    async def test_splits_long_message_on_newlines(self):
        repo = make_repo()
        thread = make_thread("test")

        # Build a message over 2000 chars by using long lines separated by newlines
        line = "a" * 1000
        content = f"{line}\n{line}\n{line}"  # 3002 chars total

        await repo.send_to_thread(thread, content)

        assert thread.send.call_count == 3
        calls = [call.args[0] for call in thread.send.call_args_list]
        # Each chunk should be at most 1990 chars
        for chunk in calls:
            assert len(chunk) <= 1990

    async def test_preserves_content_across_splits(self):
        repo = make_repo()
        thread = make_thread("test")

        line_a = "a" * 1000
        line_b = "b" * 1000
        line_c = "c" * 500
        content = f"{line_a}\n{line_b}\n{line_c}"

        await repo.send_to_thread(thread, content)

        calls = [call.args[0] for call in thread.send.call_args_list]
        combined = "\n".join(calls)
        assert line_a in combined
        assert line_b in combined
        assert line_c in combined

    async def test_sends_2001_char_message_in_two_chunks(self):
        repo = make_repo()
        thread = make_thread("test")

        # Two lines of 1001 chars each = 2003 chars with newline, which exceeds limit
        line = "x" * 1001
        content = f"{line}\n{line}"

        await repo.send_to_thread(thread, content)

        assert thread.send.call_count == 2
