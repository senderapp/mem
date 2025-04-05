import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import json
import datetime
from datetime import timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

load_dotenv()

# Replace the single TARGET_GUILD_ID with a list of guild IDs
TARGET_GUILD_IDS = [
    492024679998160907,  # First guild to monitor
    
]

# Add the notification channel ID where you want to send alerts
NOTIFICATION_CHANNEL_ID = 1358197044036112395

# Get token from environment variable
token = os.getenv("USER_AUTH_TOKEN")
if token is None:
    raise ValueError("USER_AUTH_TOKEN environment variable not set")

# File to store member data
MEMBERS_FILE = "members.json"

# Create client
client = commands.Bot(command_prefix='>', self_bot=True)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")
    # Start the periodic check when the bot is ready
    client.loop.create_task(check_for_new_members())

@client.event
async def on_message(message):
    # Only monitor messages in the specified guild
    if message.guild and message.guild.id in TARGET_GUILD_IDS:
        print(f"💬 {message.author.name}: {message.content}")
    
    await client.process_commands(message)

# Load members from JSON file
def load_members():
    if os.path.exists(MEMBERS_FILE):
        try:
            with open(MEMBERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading members file: {e}")
    return {}

# Save members to JSON file
def save_members(members_data):
    try:
        with open(MEMBERS_FILE, 'w') as f:
            json.dump(members_data, f, indent=2)
    except Exception as e:
        print(f"Error saving members file: {e}")

# Process a member object and extract relevant data
def process_member(member, current_time):
    return {
        "id": member.id,
        "name": member.name,
        "discriminator": getattr(member, "discriminator", "0"),
        "bot": member.bot,
        "nick": member.nick,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        "last_seen": current_time
    }

# Check if a member is new based on joined_at timestamp
def is_new_member(member, minutes=60):
    if not member.joined_at:
        return False
    
    # Calculate the cutoff time (default: 60 minutes ago)
    cutoff_time = datetime.datetime.now(datetime.timezone.utc) - timedelta(minutes=minutes)
    
    # Check if the member joined after the cutoff time
    return member.joined_at > cutoff_time

# Send notification about new member to another server

async def send_notification(member, guild):
    if NOTIFICATION_CHANNEL_ID == 0:
        print("Notification channel ID not set. Skipping notification.")
        return
    
    try:
        channel = client.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel:
            print(f"Could not find notification channel with ID {NOTIFICATION_CHANNEL_ID}")
            return
            
        # Check if channel is a text channel
        if not isinstance(channel, discord.TextChannel):
            print(f"Channel {getattr(channel, 'name', 'Unknown')} is not a text channel (type: {type(channel).__name__})")
            return
        
        # Format the join date and account creation date nicely
        joined_at = member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if member.joined_at else "Unknown"
        created_at = member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(member, 'created_at') and member.created_at else "Unknown"
        
        # Calculate account age if possible
        account_age = ""
        if hasattr(member, 'created_at') and member.created_at:
            days_old = (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days
            account_age = f" ({days_old} days old)"
        
        # Send formatted text message with emojis and better spacing
        plain_text = (
            f"## 🚀 NEW MEMBER DETECTED 🚀\n\n"
            f"### User Information\n"
            f"👤 **Name:** {member.name}\n"
            f"🆔 **ID:** `{member.id}`\n"
            f"📅 **Joined at:** {joined_at}\n"
            f"🗓️ **Account created:** {created_at}{account_age}\n"
            f"🤖 **Bot:** {'Yes ✓' if member.bot else 'No ✗'}\n"
            f"📝 **Nickname:** {member.nick if member.nick else 'None'}\n\n"
            f"### Server Information\n"
            f"🏠 **Server:** {guild.name}\n"
            f"👥 **Member count:** {guild.member_count if hasattr(guild, 'member_count') else 'Unknown'}\n\n"
            f"*Detected by Member Monitor at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        
        await channel.send(plain_text)
        print(f"Sent notification about new member {member.name} to channel {channel.name}")
        
    except Exception as e:
        print(f"Error sending notification: {e}")
        import traceback
        traceback.print_exc()

# Periodic check for new members
async def check_for_new_members():
    print("Starting periodic member check...")
    
    # Wait a bit to ensure client is fully ready
    await asyncio.sleep(5)
    
    # Load existing members data
    members_data = load_members()
    
    # Initial check for all guilds
    for TARGET_GUILD_ID in TARGET_GUILD_IDS:
        guild = client.get_guild(TARGET_GUILD_ID)
        
        if not guild:
            print(f"Could not find guild with ID {TARGET_GUILD_ID}")
            continue
        
        guild_members = members_data.get(str(TARGET_GUILD_ID), {})
        
        # Get current timestamp for new members
        current_time = datetime.datetime.now().isoformat()
        
        print(f"Checking for members in {guild.name}...")
        
        # Initial member count from cache
        cached_members = set(member.id for member in guild.members)
        print(f"Initial cached member count: {len(cached_members)}")
        
        # Try to get all members
        try:
            print(f"Fetching members for {guild.name}...")
            
            # Get all members from the guild
            all_members = {}
            member_count = 0
            new_members_count = 0
            
            # Fetch members
            members = await guild.fetch_members()
            for member in members:
                member_data = process_member(member, current_time)
                all_members[str(member.id)] = member_data
                member_count += 1
                
                # Check if this is a new member based on joined_at timestamp
                if is_new_member(member, minutes=60):  # Consider members who joined in the last hour as new
                    new_members_count += 1
                    print(f"\n🚀 NEW MEMBER DETECTED:")
                    print(f"  Name: {member.name}")
                    print(f"  ID: {member.id}")
                    print(f"  Server: {guild.name}")
                    print(f"  Joined at: {member.joined_at.isoformat()}")
                    print(f"  Account created: {member.created_at.isoformat() if hasattr(member, 'created_at') else 'Unknown'}")
                    print(f"  Bot: {'Yes' if member.bot else 'No'}")
                    print(f"  Nickname: {member.nick if member.nick else 'None'}")
                    print(f"  Roles: {', '.join([role.name for role in member.roles[1:]]) if len(member.roles) > 1 else 'None'}")
                    print(f"  Avatar: {'Yes' if member.avatar else 'No'}")
                    print("  " + "-"*50)
                    
                    # Send notification to another server
                    await send_notification(member, guild)
                
                # Print progress every 100 members
                if member_count % 100 == 0:
                    print(f"Processed {member_count} members so far...")
            
            print(f"Successfully fetched {len(all_members)} members from {guild.name}")
            print(f"Found {new_members_count} members who joined in the last hour")
            
            # Update our saved data
            members_data[str(TARGET_GUILD_ID)] = all_members
            save_members(members_data)
            print(f"Saved {len(all_members)} members to {MEMBERS_FILE}")
            
        except Exception as e:
            print(f"Error fetching members for guild {guild.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Continue checking periodically
    while not client.is_closed():
        try:
            print(f"Waiting 60 seconds before next check...")
            await asyncio.sleep(60)  # Check every minute
            
            print(f"Performing periodic check for new members...")
            
            # Check all target guilds
            for TARGET_GUILD_ID in TARGET_GUILD_IDS:
                guild = client.get_guild(TARGET_GUILD_ID)
                if not guild:
                    print(f"Could not find guild with ID {TARGET_GUILD_ID}")
                    continue
                    
                # Load current data
                members_data = load_members()
                guild_members = members_data.get(str(TARGET_GUILD_ID), {})
                current_time = datetime.datetime.now().isoformat()
                
                print(f"Checking guild: {guild.name}")
                
                # Get all current members
                all_members = {}
                member_count = 0
                new_members_count = 0
                
                # Fetch members
                members = await guild.fetch_members()
                for member in members:
                    member_data = process_member(member, current_time)
                    all_members[str(member.id)] = member_data
                    member_count += 1
                    
                    # Check if this is a new member based on joined_at timestamp
                    # For periodic checks, only look at the last few minutes
                    if is_new_member(member, minutes=2):  # Consider members who joined in the last 2 minutes as new
                        new_members_count += 1
                        print(f"\n🚀 NEW MEMBER DETECTED:")
                        print(f"  Name: {member.name}")
                        print(f"  ID: {member.id}")
                        print(f"  Server: {guild.name}")
                        print(f"  Joined at: {member.joined_at.isoformat()}")
                        print(f"  Account created: {member.created_at.isoformat() if hasattr(member, 'created_at') else 'Unknown'}")
                        print(f"  Bot: {'Yes' if member.bot else 'No'}")
                        print(f"  Nickname: {member.nick if member.nick else 'None'}")
                        print(f"  Roles: {', '.join([role.name for role in member.roles[1:]]) if len(member.roles) > 1 else 'None'}")
                        print(f"  Avatar: {'Yes' if member.avatar else 'No'}")
                        print("  " + "-"*50)
                        
                        # Send notification to another server
                        await send_notification(member, guild)
                    
                    # Print progress less frequently during periodic checks
                    if member_count % 500 == 0:
                        print(f"Processed {member_count} members so far...")
                
                print(f"Successfully fetched {len(all_members)} members in {guild.name}")
                print(f"Found {new_members_count} new members who joined in the last 2 minutes")
                
                # Update our saved data
                members_data[str(TARGET_GUILD_ID)] = all_members
                save_members(members_data)
                
        except Exception as e:
            print(f"Error during member check: {e}")
            import traceback
            traceback.print_exc()


# Create a dummy web server to please Render


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Selfbot is running.")

def run_server():
    port = int(os.environ.get("PORT", 8080))  # Render expects this
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# Start the dummy web server in a background thread
threading.Thread(target=run_server).start()
# Run the client with your user token
client.run(token)
