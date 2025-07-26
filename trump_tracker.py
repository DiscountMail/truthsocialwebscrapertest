# --- START OF FILE trump_tracker.py ---
import subprocess
import discord
from discord.ext import tasks
import asyncio
import os
from collections import deque
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import traceback
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv() # Load environment variables from .env file

# Get secrets from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
URL = "https://civictracker.us/executive/member/?uuid=3094abf7-4a95-4b8d-8c8d-af7d1c3747a1"
CHECK_INTERVAL_SECONDS = 600

# --- Bot Setup ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
sent_truth_urls = deque(maxlen=50)

# --- Synchronous Scraping Function using Playwright ---
def scrape_with_playwright(url):
    html_content = None
    print("Starting Playwright thread...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            print("Applying resource blocking rules...")
            def block_resources(route):
                if route.request.resource_type in ["image", "stylesheet", "font", "media"]:
                    route.abort()
                else:
                    route.continue_()
            
            page.route("**/*", block_resources)

            print(f"Navigating to URL: {url}")
            page.goto(url, timeout=60000)
            
            print("Waiting for post selector to appear...")
            page.wait_for_selector('div.social-post', timeout=30000)
            
            print("Posts found. Getting page content...")
            html_content = page.content()
            browser.close()
    except Exception as e:
        print(f"An error occurred in the Playwright thread: {e}")
        traceback.print_exc()
    
    print("Playwright thread finished.")
    return html_content


@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def scrape_and_send():
    await client.wait_until_ready()
    channel = client.get_channel(int(CHANNEL_ID)) # Convert to int
    if not channel:
        print(f"Error: Channel with ID {CHANNEL_ID} not found.")
        return

    print("-----------------------------------")
    print(f"Dispatching optimized Playwright scraper to background thread...")
    
    loop = asyncio.get_running_loop()
    rendered_html = await loop.run_in_executor(None, scrape_with_playwright, URL)

    if not rendered_html:
        print("Playwright scraper failed or returned no HTML.")
        return

    print("Parsing HTML returned from Playwright thread...")
    soup = BeautifulSoup(rendered_html, 'html.parser')
    posts = soup.find_all('div', class_='social-post')

    if not posts:
        print("No posts found in the rendered HTML.")
        return

    print(f"Found {len(posts)} posts. Processing...")
    
    for post in reversed(posts[:30]):
        try:
            original_post_link_tag = post.find('a', class_='post-link')
            if not original_post_link_tag or 'href' not in original_post_link_tag.attrs:
                continue
            original_post_url = original_post_link_tag['href']

            if original_post_url in sent_truth_urls:
                continue

            print(f"Found new post: {original_post_url}")
            
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
            print(f"Error parsing a single post: {e}")
            traceback.print_exc()

@client.event
async def on_ready():
    print("===================================")
    print(f'Logged in as {client.user.name}')
    print(f"Now monitoring CivicTracker with Playwright: {URL}")
    print(f"Sending updates to channel ID: {CHANNEL_ID}")
    print("===================================")
    scrape_and_send.start()

def main():
    # --- Critical Check for Secrets ---
    if not BOT_TOKEN or not CHANNEL_ID:
        print("FATAL ERROR: BOT_TOKEN and/or CHANNEL_ID not found in environment variables.")
        print("Please create a .env file or set the variables on your hosting service.")
        return

    try:
        # --- Install Playwright Browser at Runtime ---
        print("Ensuring Playwright browser is installed...")
        # Using subprocess.run to execute the command.
        # Using "shell=True" might be necessary on some systems but try without it first.
        # For Render's Linux environment, a list of args is more robust.
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("Browser installation check complete.")

        client.run(BOT_TOKEN)
    except subprocess.CalledProcessError as e:
        print(f"FATAL ERROR: Failed to install Playwright browser. {e}")
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
