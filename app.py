# --- START OF FILE app.py ---

import discord
from discord.ext import tasks
import asyncio
import os
from collections import deque
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import traceback
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# --- Load Environment Variables ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
URL = "https://civictracker.us/executive/member/?uuid=3094abf7-4a95-4b8d-8c8d-af7d1c3747a1"
CHECK_INTERVAL_SECONDS = 600

# ==============================================================================
#  1. FLASK WEB SERVER SETUP
# ==============================================================================
app = Flask('')

@app.route('/')
def home():
    """This route is called by Render's health checks and keeps the service alive."""
    return "Scraper bot web server is alive."

# ==============================================================================
#  2. DISCORD BOT AND SCRAPER LOGIC
# ==============================================================================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
sent_truth_urls = deque(maxlen=50)

def scrape_with_playwright(url):
    html_content = None
    print("Starting Playwright thread...", flush=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            print("Applying resource blocking rules...", flush=True)
            def block_resources(route):
                if route.request.resource_type in ["image", "stylesheet", "font", "media"]:
                    route.abort()
                else:
                    route.continue_()
            
            page.route("**/*", block_resources)

            print(f"Navigating to URL: {url}", flush=True)
            page.goto(url, timeout=60000)
            
            print("Waiting for post selector to appear...", flush=True)
            page.wait_for_selector('div.social-post', timeout=30000)
            
            print("Posts found. Getting page content...", flush=True)
            html_content = page.content()
            browser.close()
    except Exception as e:
        print(f"An error occurred in the Playwright thread: {e}", flush=True)
        traceback.print_exc()
    
    print("Playwright thread finished.", flush=True)
    return html_content

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def scrape_and_send():
    await client.wait_until_ready()
    channel = client.get_channel(int(CHANNEL_ID))
    if not channel:
        print(f"Error: Channel with ID {CHANNEL_ID} not found.", flush=True)
        return

    print("-----------------------------------", flush=True)
    print(f"Dispatching optimized Playwright scraper...", flush=True)
    
    loop = asyncio.get_running_loop()
    rendered_html = await loop.run_in_executor(None, scrape_with_playwright, URL)

    if not rendered_html:
        print("Playwright scraper failed or returned no HTML.", flush=True)
        return

    print("Parsing HTML returned...", flush=True)
    soup = BeautifulSoup(rendered_html, 'html.parser')
    posts = soup.find_all('div', class_='social-post')

    if not posts:
        print("No posts found in the rendered HTML.", flush=True)
        return

    print(f"Found {len(posts)} posts. Processing...", flush=True)
    
    for post in reversed(posts[:30]):
        try:
            # ... (the rest of the parsing logic is identical and correct)
            original_post_link_tag = post.find('a', class_='post-link')
            if not original_post_link_tag or 'href' not in original_post_link_tag.attrs:
                continue
            original_post_url = original_post_link_tag['href']
            if original_post_url in sent_truth_urls:
                continue
            print(f"Found new post: {original_post_url}", flush=True)
            post_content_tag = post.find('div', class_='post-content')
            post_text = post_content_tag.get_text(separator='\n', strip=True) if post_content_tag else "No text content."
            timestamp_tag = post.find('div', class_='post-date-bottom')
            timestamp = timestamp_tag.get_text(strip=True) if timestamp_tag else "Timestamp not available."
            author_name_tag = post.find('div', class_='post-username')
            author_name = author_name_tag.get_text(strip=True) if author_name_tag else "Donald J. Trump"
            author_avatar_tag = post.find('img', class_='post-avatar')
            author_avatar_url = author_avatar_tag['src'] if author_avatar_tag and 'src' in author_avatar_tag.attrs else None
            embed = discord.Embed(description=post_text, color=discord.Color.blue(), url=original_post_url)
            embed.set_author(name=author_name, icon_url=author_avatar_url, url=original_post_url)
            embed.set_footer(text=f"Posted: {timestamp} | via civictracker.us")
            media_link, is_video = None, False
            media_container = post.find('div', class_='post-media')
            if media_container:
                image_tag = media_container.find('img')
                video_source_tag = media_container.find('source')
                if image_tag and 'src' in image_tag.attrs:
                    embed.set_image(url=image_tag['src'])
                elif video_source_tag and 'src' in video_source_tag.attrs:
                    media_link = video_source_tag['src']
                    is_video = True
            await channel.send(embed=embed)
            if is_video and media_link:
                await channel.send(f"Video from post: {media_link}")
            sent_truth_urls.append(original_post_url)
        except Exception as e:
            print(f"Error parsing a single post: {e}", flush=True)
            traceback.print_exc()

@client.event
async def on_ready():
    print("===================================", flush=True)
    print(f'Logged in as {client.user.name}', flush=True)
    print(f"Bot is ready and starting the scraper loop.", flush=True)
    print("===================================", flush=True)
    scrape_and_send.start()

# ==============================================================================
#  3. THREADING AND EXECUTION LOGIC
# ==============================================================================
def run_bot():
    """Target function for the bot's thread. This is a blocking call."""
    if not BOT_TOKEN or not CHANNEL_ID:
        print("FATAL: Cannot start bot. Missing BOT_TOKEN or CHANNEL_ID.", flush=True)
        return
    client.run(BOT_TOKEN)

# This code runs when Gunicorn imports this file.
# It starts the Discord bot in a separate, non-blocking thread.
print("Starting Discord bot in a background thread...", flush=True)
bot_thread = Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

# Gunicorn will not run the code below. This is for local testing.
if __name__ == '__main__':
    print("Running in local development mode.", flush=True)
    # This will run the web server for local testing.
    # The bot is already started by the code above.
    app.run(host='0.0.0.0', port=8080)