# Matrix-Status-Bot
A Matrix Maubot bot that lets you observe the online/offline status of your services.


## Setup
1. Create a file, named base-config.yaml
2. Enter your accountID and the roomID of your chat with the bot.
3. Build the Plugin with `mbc Build`.
4. Upload the plugin to your Maubot instance
<pre><code>allowed:
  [["@user:matrix.server.de"], ["RoomID:server02.de"]]
</code></pre>

## Feature
* user management
* request all kinds of services
* add and remove services without recompiling the plugin
* add and remove authorized users without recompiling the plugin