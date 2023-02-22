# Matrix-Status-Bot
A Matrix Maubot bot that lets you observe the online/offline status of your services.


## Setup
1. Create a file, named base-config.yaml
2. Enter your accountID and the roomID of your chat with the bot
   * Everybody listed in the base-config file is allowed to authorize users to also use the bot
   * Notice. you need to grant yourself access to the bot, even when you are in the base-config
<pre><code>allowed:
  [["@user:matrix.server.de"], ["RoomID:server02.de"]]
</code></pre>
3. Build the Plugin with `mbc Build`
4. Upload the plugin to your Maubot instance

## Features
* user management
* request all kinds of services
* add and remove services without recompiling the plugin
* add and remove authorized users without recompiling the plugin

## Commands
### Admin
* Authorize an account to use the bot `!admin authorize <user>` e.x `!admin authorrize @exampleuser.matrix.example.com`
* Deauthorize an account `!admin deauthorize <user>` e.x `!admin deauthorrize @exampleuser.matrix.example.com`
* Search for a specific authorized user `!admin get <user>` e.x `!admin get @exampleuser.matrix.example.com`
* List the authoried users `!admin list <user>` e.x `!admin list @exampleuser.matrix.example.com`

### Status
* Add a web service `!status addweb <domain> <port>` e.x `!status addweb example.com 80`
* Add a non web service `!status addnoweb <domain> <port>` e.x `!status addnoweb example.com 22`
* Remove a service `!status rem <domain> <port>` e.x `!status rem example.com 25`
* List the services you currently observe `status list`
* Request the status of your services `!status ping`