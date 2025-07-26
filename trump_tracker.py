import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks
import asyncio
import os
from collections import deque

# --- Configuration ---
# It's recommended to use environment variables for sensitive data in a production environment
BOT_TOKEN = os.environ.get("BOT_TOKEN", "MTMzNDI3MzU1NDQ5NzQwNDk2OA.GLtctF.qZr4LymhqwVnqQ_K-UNtKd62TZekRR_g0rf-GE")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1398016564845875391"))
URL = "https://trumpstruth.org/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
CHECK_INTERVAL_SECONDS = 600  # Check every 10 minutes

# --- Discord Bot Setup ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Use a deque to store the URLs of the last 25 sent truths to avoid duplicates
# This also prevents the set from growing indefinitely.
sent_truth_urls = deque(maxlen=25)

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def scrape_and_send():
    """
    Scrapes the website for new truths and sends them to Discord.
    This function runs periodically as a background task.
    """
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Channel with ID {CHANNEL_ID} not found. Will retry later.")
        return

    print("-----------------------------------")
    print("Scraping for new truths...")
    
    try:
        # Use a timeout to prevent the script from hanging
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        print("Request successful, parsing HTML...")

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all status containers
        statuses = soup.find_all('div', class_='status')
        
        if not statuses:
            print("No statuses found on the page.")
            return

        print(f"Found {len(statuses)} statuses. Checking the most recent 3...")
        
        truths_to_send = []
        for status in reversed(statuses[:3]):  # Reverse to send oldest of the newest first
            status_url = status.get('data-status-url', '').strip()
            
            # If we don't have a unique URL for the status, we can't track it.
            # Also, if we've already sent it, skip.
            if not status_url or status_url in sent_truth_urls:
                continue

            text_element = status.find('div', class_='status__content')
            text = text_element.get_text(strip=True) if text_element and text_element.get_text(strip=True) else "No text content."

            timestamp_element = status.find('a', class_='status-info__meta-item', href=lambda href: href and 'statuses' in href)
            timestamp = timestamp_element.get_text(strip=True) if timestamp_element else "Timestamp not available."

            # Look for an image in the attachments
            image_url = None
            attachments = status.find('div', class_='status__attachments')
            if attachments:
                image_tag = attachments.find('img')
                if image_tag and image_tag.has_attr('src'):
                    image_url = image_tag['src']

            # Create the embed
            embed = discord.Embed(
                title="New Truth from Donald J. Trump",
                description=text,
                color=discord.Color.blue(),
                url=status_url
            )
            if image_url:
                embed.set_image(url=image_url)
            
            embed.set_footer(text=f"Posted: {timestamp}")
            
            truths_to_send.append({'embed': embed, 'url': status_url})

        if truths_to_send:
            print(f"Found {len(truths_to_send)} new truths to send.")
            for truth in truths_to_send:
                await channel.send(embed=truth['embed'])
                sent_truth_urls.append(truth['url']) # Mark as sent
        else:
            print("No new truths found since last check.")

    except requests.exceptions.Timeout:
        print("Error: The request to trumpstruth.org timed out.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")

@client.event
async def on_ready():
    """
    Event handler for when the bot logs in and is ready.
    """
    print("===================================")
    print(f'Logged in as {client.user.name}')
    print(f"Monitoring {URL} for posts.")
    print(f"Sending updates to channel ID: {CHANNEL_ID}")
    print("===================================")
    scrape_and_send.start() # Start the background task loop

async def main():
    """
    Main function to run the bot.
    """
    if not BOT_TOKEN or not CHANNEL_ID:
        print("Error: Please set your BOT_TOKEN and CHANNEL_ID.")
        return
        
    try:
        await client.start(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord Bot Token. Please check your BOT_TOKEN.")
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
