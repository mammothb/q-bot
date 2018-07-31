# QBot
A self-host Discord bot to format quoted user message as a code block

Majority of the code is adapted from [MEE6](https://github.com/cookkkie/mee6). Majority of the code modifications were made to remove the dependency on redis and to enable running an instance of the bot for single server use.

## Implemented plugins and modules
* Help (Adapted from MEE6)
  * Displays plugin usage information using Embeds
* Quote
  * Quotes target message (by ID) and format it as a code block
* Search
  * Twitch (From MEE6)
    * Searches Twitch for the streamer by channel name
  * Urban dictionary
    * Searches for the top definition for the given phrase
  * Wikipedia
    * Searches for the top page for the given phrase
  * YouTube (From MEE6)
    * Searches for the top video for the given phrase
* Streamer (Adapted from MEE6)
  * Tracks Twitch streamers only
  * Stores information locally using SQLite
* Youtuber
  * Tracks YouTube channels and announce when they post a new video
  * Checks hourly
  * Stores information locally using SQLite
