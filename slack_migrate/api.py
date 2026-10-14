import os
import json
import time
from pathlib import Path
from slack_bolt import App
from slack_sdk import WebClient
from dotenv import load_dotenv
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Add rate limit handler to app client
rate_limit_handler = RateLimitErrorRetryHandler(max_retry_count=1)
app.client.retry_handlers.append(rate_limit_handler)

admin_client = WebClient(token=os.environ.get("SLACK_USER_TOKEN"))

# Add rate limit handler to admin client
admin_client.retry_handlers.append(rate_limit_handler)

# Cache directory
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def get_cached_data(cache_name):
    """Get data from cache if it exists and is valid.

    Args:
        cache_name (str): Name of the cache file (without extension)

    Returns:
        dict: Cached data or None if no valid cache exists
    """
    cache_file = CACHE_DIR / f"{cache_name}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            cache_data = json.load(f)
            return cache_data["data"]
    except Exception as e:
        raise Exception(f"Error reading cache file {cache_file}: {e}")


def cache_data(cache_name, data):
    """Save data to cache with timestamp.

    Args:
        cache_name (str): Name of the cache file (without extension)
        data: Data to cache
    """
    cache_file = CACHE_DIR / f"{cache_name}.json"

    try:
        cache_content = {
            "timestamp": time.time(),
            "data": data
        }

        with open(cache_file, "w") as f:
            json.dump(cache_content, f)
    except Exception as e:
        raise Exception(f"Error writing to cache file {cache_file}: {e}")


def fetch_emoji(refresh=False):
    """Fetch all custom emoji from the workspace.

    Args:
        refresh (bool): Force refresh of cached data

    Returns:
        dict: Dictionary of emoji names and their URLs
    """
    cache_name = "emoji"

    if not refresh:
        cached_emoji = get_cached_data(cache_name)
        if cached_emoji is not None:
            return cached_emoji

    try:
        result = app.client.emoji_list()

        emoji_dict = result.get("emoji", {})

        cache_data(cache_name, emoji_dict)

        return emoji_dict
    except Exception as e:
        raise Exception(f"Error retrieving emoji: {e}")


def fetch_users(refresh=False):
    """Fetch all users from the workspace.

    Args:
        refresh (bool): Force refresh of cached data

    Returns:
        list: List of all user objects
    """
    cache_name = "users"

    if not refresh:
        cached_users = get_cached_data(cache_name)
        if cached_users is not None:
            return cached_users

    users = []
    cursor = None

    try:
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor

            result = app.client.users_list(**params)

            users_batch = result["members"]
            users.extend(users_batch)

            cursor = result.get("response_metadata", {}).get("next_cursor")

            if not cursor:
                break

        cache_data(cache_name, users)
        return users

    except Exception as e:
        raise Exception(f"Error retrieving all users: {e}")


def fetch_user_info(user_id, refresh=False):
    """Fetch information about a specific user.

    Args:
        user_id (str): The Slack user ID to look up
        refresh (bool): Force refresh of all users data

    Returns:
        dict: User information or empty dict if not found/error
    """
    all_users = fetch_users(refresh=refresh)

    for user in all_users:
        if user["id"] == user_id:
            return user

    return {}


def enrich_channels_with_creator_info(channels):
    """Enrich channel objects with creator user details.

    Args:
        channels (list): List of channel objects

    Returns:
        list: Channels with enriched creator information
    """
    # Get all users
    users = fetch_users()

    # Create a mapping of user IDs to user objects for efficient lookup
    user_map = {user['id']: user for user in users}

    # Enrich each channel with creator details
    for channel in channels:
        creator_id = channel.get('creator')
        if creator_id and creator_id in user_map:
            user = user_map[creator_id]
            profile = user.get('profile', {})

            # Replace creator ID with structured object
            channel['creator'] = {
                'id': creator_id,
                'real_name': user.get('real_name', ''),
                'email': profile.get('email', ''),
                'display_name': profile.get('display_name', '')
            }
        else:
            channel['creator'] = {
                'id': creator_id,
                'real_name': None,
                'email': None,
                'display_name': None
            }

    return channels


def fetch_channels(refresh=False):
    """Core function to fetch all public channels with pagination.

    Args:
        refresh (bool): Force refresh of cached data

    Returns:
        list: List of all channel objects with enriched creator info
    """
    cache_name = "channels"

    # Check cache first if not forcing refresh
    if not refresh:
        cached_channels = get_cached_data(cache_name)
        if cached_channels is not None:
            return cached_channels

    channels = []
    cursor = None

    while True:
        try:
            params = {
                "types": "public_channel",
                "limit": 100
            }

            if cursor:
                params["cursor"] = cursor

            result = app.client.conversations_list(**params)

            channels_batch = result["channels"]
            channels.extend(channels_batch)

            cursor = result.get("response_metadata", {}).get("next_cursor")

            if not cursor:
                break

        except Exception as e:
            raise Exception(f"Error retrieving channels: {e}")

    enriched_channels = enrich_channels_with_creator_info(channels)

    cache_data(cache_name, enriched_channels)

    return enriched_channels


def get_channel_info(channel_id):
    """Get information about a Slack channel.

    Args:
        channel_id (str): ID of the channel

    Returns:
        dict: Channel information

    Raises:
        Exception: If API call fails with an error
    """
    try:
        response = app.client.conversations_info(channel=channel_id)
        if response.get('ok', False):
            return response.get('channel', {})
        else:
            raise Exception(response.get('error', 'Unknown error'))
    except Exception as e:
        raise Exception(f"Error getting channel info: {str(e)}")


def rename_channel(channel_id, new_name):
    """Rename a Slack channel using Bolt.

    Args:
        channel_id (str): ID of the channel to rename
        new_name (str): New name for the channel (without the # prefix)

    Returns:
        bool: True if successful, False otherwise

    Raises:
        Exception: If API call fails with an error
    """
    try:
        channel_info = get_channel_info(channel_id)
        is_member = channel_info.get('is_member', False)

        if not is_member:
            try:
                if not channel_info.get('is_private', True):
                    admin_client.conversations_join(channel=channel_id)
                else:
                    raise Exception(
                        f"Bot is not a member of private channel {channel_id}. Please invite the bot first.")
            except Exception as e:
                raise Exception(
                    f"Failed to join channel {channel_id}: {str(e)}")

        if new_name.startswith('#'):
            new_name = new_name[1:]

        response = admin_client.conversations_rename(
            channel=channel_id,
            name=new_name
        )
        return response.get('ok', False)

    except Exception as e:
        raise Exception(f"Error renaming channel {channel_id}: {str(e)}")


def archive_channel(channel_id):
    """Archive a Slack channel using Bolt.

    Args:
        channel_id (str): ID of the channel to archive

    Returns:
        bool: True if successful, False otherwise

    Raises:
        Exception: If API call fails with an error
    """
    try:
        channel_info = get_channel_info(channel_id)
        is_member = channel_info.get('is_member', False)

        if not is_member:
            try:
                if not channel_info.get('is_private', True):
                    app.client.conversations_join(channel=channel_id)
                else:
                    raise Exception(
                        f"Bot is not a member of private channel {channel_id}. Please invite the bot first.")
            except Exception as e:
                raise Exception(
                    f"Failed to join channel {channel_id}: {str(e)}")

        response = app.client.conversations_archive(channel=channel_id)
        return response.get('ok', False)

    except Exception as e:
        raise Exception(f"Error archiving channel {channel_id}: {str(e)}")


CANVAS_FILETYPE = "quip"


def _channel_canvas_ids(channels):
    """Map channel canvas file IDs to the channel that owns them."""
    owners = {}
    for channel in channels:
        try:
            info = get_channel_info(channel["id"])
        except Exception:
            continue
        canvas = (info.get("properties") or {}).get("canvas") or {}
        file_id = canvas.get("file_id")
        if file_id:
            owners[file_id] = channel["id"]
    return owners


def fetch_canvases(refresh=False):
    """Fetch all canvases visible to the token.

    Args:
        refresh (bool): Force refresh of cached data

    Returns:
        list: Canvas file objects, each with an added "channel_id" key
            (None unless the canvas is a channel canvas)
    """
    cache_name = "canvases"

    if not refresh:
        cached = get_cached_data(cache_name)
        if cached is not None:
            return cached

    canvases = []
    page = 1

    try:
        while True:
            result = app.client.files_list(
                types=CANVAS_FILETYPE, count=100, page=page)
            canvases.extend(
                f for f in result["files"]
                if f.get("filetype") == CANVAS_FILETYPE)

            paging = result.get("paging", {})
            if page >= paging.get("pages", 1):
                break
            page += 1

        owners = _channel_canvas_ids(fetch_channels(refresh=refresh))
        for canvas in canvases:
            canvas["channel_id"] = owners.get(canvas["id"])

        cache_data(cache_name, canvases)
        return canvases

    except Exception as e:
        raise Exception(f"Error retrieving canvases: {e}")


def download_canvas_content(file_id):
    """Download the HTML content of a canvas.

    Args:
        file_id (str): ID of the canvas file

    Returns:
        str: Canvas HTML

    Raises:
        Exception: If the canvas cannot be read
    """
    import urllib.request

    try:
        response = app.client.files_info(file=file_id)
        url = response["file"].get("url_private_download") or \
            response["file"].get("url_private")
        if not url:
            raise Exception("canvas has no download URL")

        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {app.client.token}"})
        with urllib.request.urlopen(request) as http_response:
            return http_response.read().decode("utf-8")
    except Exception as e:
        raise Exception(f"Error downloading canvas {file_id}: {e}")


def create_canvas(title, markdown, channel_id=None):
    """Create a canvas, standalone or as a channel's canvas.

    Args:
        title (str): Canvas title (standalone canvases only)
        markdown (str): Canvas content as markdown
        channel_id (str): If given, create the channel canvas for this channel

    Returns:
        str: ID of the new canvas

    Raises:
        Exception: If API call fails with an error
    """
    content = {"type": "markdown", "markdown": markdown}
    try:
        if channel_id:
            response = admin_client.conversations_canvases_create(
                channel_id=channel_id, document_content=content)
        else:
            response = admin_client.canvases_create(
                title=title, document_content=content)

        if not response.get("ok", False):
            raise Exception(response.get("error", "Unknown error"))
        return response["canvas_id"]
    except Exception as e:
        raise Exception(f"Error creating canvas '{title}': {e}")
