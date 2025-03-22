import discord


def search(source: str, target: str):
    """
    Use a smart search to compare two strings.
    """
    for word in target.split():
        if word.lower() not in source.lower():
            return False
    return True


async def get_channel(guild: discord.Guild, channel_id: int) -> discord.Thread | discord.TextChannel | None:
    """
    Get a channel from a guild.
    """
    _channel = guild.get_channel(channel_id)
    _thread = guild.get_thread(channel_id)

    channel = _channel or _thread

    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except discord.NotFound:
            channel = None

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        channel = None

    return channel
