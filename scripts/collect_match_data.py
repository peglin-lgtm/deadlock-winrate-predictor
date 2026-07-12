import asyncio
import json

import aiohttp
from aiolimiter import AsyncLimiter


BASE_URL = "https://api.deadlock-api.com/v1/matches"
OUTPUT_FILE = "data/matches_metadata.jsonl"


class CloudflareBlockedError(Exception):
    """Raised when Cloudflare blocks further API requests."""
    pass


async def load_matches_async(
    match_ids: list[int],
    requests_per_second: int = 5,
    concurrent_requests: int = 5,
) -> int:

    # Keep request throughput within the API rate limit.
    limiter = AsyncLimiter(
        requests_per_second,
        time_period=1,
    )

    semaphore = asyncio.Semaphore(
        concurrent_requests
    )

    timeout = aiohttp.ClientTimeout(total=30)

    connector = aiohttp.TCPConnector(
        limit=concurrent_requests
    )

    async def load_one_match(
        session: aiohttp.ClientSession,
        match_id: int,
    ) -> dict | None:

        url = f"{BASE_URL}/{match_id}/metadata"

        for attempt in range(5):
            try:
                async with limiter:
                    async with semaphore:
                        async with session.get(url) as response:

                            if response.status == 200:
                                data = await response.json()

                                data["match_id"] = match_id

                                return data

                            text = await response.text()

                            if response.status == 403:
                                print(
                                    f"\nMatch {match_id}: "
                                    f"Cloudflare returned 403"
                                )
                                print(text[:500])

                                raise CloudflareBlockedError(
                                    "IP заблокирован Cloudflare"
                                )

                            if response.status == 429:
                                wait_time = float(
                                    response.headers.get(
                                        "Retry-After",
                                        10,
                                    )
                                )

                                print(
                                    f"Match {match_id}: "
                                    f"request limit reached. "
                                    f"Retrying in {wait_time} sec."
                                )

                            elif response.status >= 500:
                                wait_time = 2 ** attempt

                                print(
                                    f"Match {match_id}: "
                                    f"server error "
                                    f"{response.status}. "
                                    f"Retrying in {wait_time} sec."
                                )

                            else:
                                print(
                                    f"Match {match_id} skipped: "
                                    f"status={response.status}"
                                )
                                print(text[:300])

                                return None

                # Back off before retrying rate-limit and server errors.
                await asyncio.sleep(wait_time)

            except CloudflareBlockedError:
                raise

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as error:

                wait_time = 2 ** attempt

                print(
                    f"Match {match_id}: {error}. "
                    f"Retrying in {wait_time} sec."
                )

                await asyncio.sleep(wait_time)

        print(
            f"Match {match_id} failed to load "
            f"after five attempts"
        )

        return None

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:

        # Process bounded chunks to limit memory usage.
        CHUNK_SIZE = 50

        # Add a longer pause between large request batches.
        PAUSE_EVERY = 250
        BATCH_PAUSE = 60

        total = len(match_ids)
        completed_total = 0
        successful_total = 0

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8",
        ) as output_file:

            for start in range(0, total, CHUNK_SIZE):
                chunk_ids = match_ids[
                    start:start + CHUNK_SIZE
                ]

                tasks = [
                    asyncio.create_task(
                        load_one_match(
                            session,
                            match_id,
                        )
                    )
                    for match_id in chunk_ids
                ]

                try:
                    for task in asyncio.as_completed(tasks):
                        match_data = await task
                        completed_total += 1

                        if match_data is not None:
                            # Stream each result to disk instead of retaining it in memory.
                            json.dump(
                                match_data,
                                output_file,
                                ensure_ascii=False,
                            )

                            output_file.write("\n")

                            successful_total += 1

                        if (
                            completed_total % 50 == 0
                            or completed_total == total
                        ):
                            print(
                                f"Processed: "
                                f"{completed_total}/{total}, "
                                f"successful: "
                                f"{successful_total}"
                            )

                except CloudflareBlockedError as error:
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                    await asyncio.gather(
                        *tasks,
                        return_exceptions=True,
                    )

                    print("\nDownload stopped.")
                    print(error)

                    output_file.flush()

                    return successful_total

                output_file.flush()

                if (
                    completed_total % PAUSE_EVERY == 0
                    and completed_total < total
                ):
                    print(
                        f"Pausing for {BATCH_PAUSE} seconds "
                        f"after {completed_total} requests"
                    )

                    await asyncio.sleep(BATCH_PAUSE)

        return successful_total


def load_matches(
    match_ids: list[int],
) -> int:

    # Preserve input order while removing duplicate match IDs.
    unique_match_ids = list(
        dict.fromkeys(match_ids)
    )

    return asyncio.run(
        load_matches_async(unique_match_ids)
    )


with open(
    "data/collected_match_ids.json",
    "r",
    encoding="utf-8",
) as file:
    match_ids = json.load(file)


successful_total = load_matches(match_ids)

print(
    f"Matches saved: {successful_total}"
)
print(
    f"File: {OUTPUT_FILE}"
)
