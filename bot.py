from __future__ import annotations

import logging
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import load_config
from notifier import send_desktop_notification
from rolimons import Deal, Item, RolimonsClient
from watchlist_db import WatchlistDB

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("deal_tracker")

config = load_config()
db = WatchlistDB()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

rolimons_client: RolimonsClient | None = None


@bot.event
async def on_ready():
    global rolimons_client
    session = aiohttp.ClientSession()
    rolimons_client = RolimonsClient(session)
    await rolimons_client.refresh_item_cache()
    refresh_item_cache_loop.start()
    poll_deals_loop.start()
    await bot.tree.sync()
    async for guild in bot.fetch_guilds():
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    log.info("Logged in as %s, tracking %d items", bot.user, rolimons_client.item_count)


@tasks.loop(seconds=config.item_cache_refresh_seconds)
async def refresh_item_cache_loop():
    await rolimons_client.refresh_item_cache()


async def notify_deal(deal: Deal) -> int:
    watchers = await db.watchers_for_asset(deal.item.asset_id)
    matching_watchers = [w for w in watchers if deal.percent_off >= w.min_percent]
    if not matching_watchers:
        return 0

    message = (
        f"{deal.item.name} sold for {deal.price:,} "
        f"({deal.percent_off:.1f}% under {deal.item.reference_price:,})"
    )
    log.info(message)

    if config.desktop_notifications_enabled:
        send_desktop_notification("Roblox Deal", message)

    for watcher in matching_watchers:
        user = await bot.fetch_user(watcher.user_id)
        try:
            await user.send(message)
        except discord.Forbidden:
            log.warning("Could not DM user %s", watcher.user_id)

    return len(matching_watchers)


@tasks.loop(seconds=config.poll_interval_seconds)
async def poll_deals_loop():
    deals = await rolimons_client.poll_new_deals()
    if not deals:
        return

    watched_ids = await db.all_watched_asset_ids()
    for deal in deals:
        if deal.item.asset_id in watched_ids:
            await notify_deal(deal)


async def item_autocomplete(interaction: discord.Interaction, current: str):
    matches = rolimons_client.find_by_name(current)
    return [app_commands.Choice(name=item.name, value=str(item.asset_id)) for item in matches]


def resolve_item(item: str) -> Item | None:
    try:
        asset_id = int(item)
    except ValueError:
        matches = rolimons_client.find_by_name(item, limit=1)
        if not matches:
            return None
        asset_id = matches[0].asset_id
    return rolimons_client.get_item(asset_id)


@bot.tree.command(name="watch", description="Get notified when a limited item has a deal")
@app_commands.describe(item="Item name", min_percent="Minimum percent off to notify at")
@app_commands.autocomplete(item=item_autocomplete)
async def watch(interaction: discord.Interaction, item: str, min_percent: float = config.default_min_percent):
    found_item = resolve_item(item)
    if found_item is None:
        await interaction.response.send_message(f"No item found matching '{item}'.", ephemeral=True)
        return

    await db.add(interaction.user.id, found_item.asset_id, found_item.name, min_percent)
    await interaction.response.send_message(
        f"Watching {found_item.name} for deals of {min_percent}% or more.", ephemeral=True
    )


@bot.tree.command(name="unwatch", description="Stop tracking a limited item")
@app_commands.describe(item="Item name")
@app_commands.autocomplete(item=item_autocomplete)
async def unwatch(interaction: discord.Interaction, item: str):
    found_item = resolve_item(item)
    if found_item is None:
        await interaction.response.send_message(f"No item found matching '{item}'.", ephemeral=True)
        return

    removed = await db.remove(interaction.user.id, found_item.asset_id)
    message = "Removed from your watchlist." if removed else "That item wasn't on your watchlist."
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="testdeal", description="Simulate a deal to test notifications")
@app_commands.describe(item="Item name", percent_off="Percent off to simulate")
@app_commands.autocomplete(item=item_autocomplete)
async def testdeal(interaction: discord.Interaction, item: str, percent_off: float = 10.0):
    found_item = resolve_item(item)
    if found_item is None:
        await interaction.response.send_message(f"No item found matching '{item}'.", ephemeral=True)
        return

    reference = found_item.reference_price
    if reference is None:
        await interaction.response.send_message(
            f"{found_item.name} has no RAP or value to compare against.", ephemeral=True
        )
        return

    price = round(reference * (1 - percent_off / 100))
    deal = Deal(item=found_item, price=price, timestamp=int(time.time()), percent_off=percent_off)
    notified = await notify_deal(deal)

    if notified:
        await interaction.response.send_message(
            f"Simulated a {percent_off}% deal on {found_item.name}, notified {notified} watcher(s).",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"Simulated a {percent_off}% deal on {found_item.name}, but nobody is watching it above that threshold.",
            ephemeral=True,
        )


@bot.tree.command(name="list", description="Show your watchlist")
async def list_watchlist(interaction: discord.Interaction):
    entries = await db.list_for_user(interaction.user.id)
    if not entries:
        await interaction.response.send_message("Your watchlist is empty.", ephemeral=True)
        return

    lines = [f"{e.item_name} — {e.min_percent}% or more" for e in entries]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


if __name__ == "__main__":
    bot.run(config.discord_token)
