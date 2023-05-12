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
* shared service list between authorized users in groups
* private service list in privat chat

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

## Private chat vs. groups
The Bot differentiates service lists by the room_id of a chat. This means a user who adds services in a private chat with the bot will have a list only he can access. If the same user is part of a group, the bot also is a member of, the authorized user can add services to a list that do not interact with his list from the private chat.
The key is that different authorized members who are part of a group can have a shared list, but also every user is able to have his/her own private list in the direct chat with the bot.

Example:
authorized users: A, B
Chats: private_A, private_B, group_ABC
possible lists: A, B, AB

IMPORTANT: User C will be able to read messages in group_ABC that are addressed to the bot! Also, the bots responses are visible to all group members.