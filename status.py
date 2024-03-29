from __future__ import annotations

import asyncio
from mautrix.util import background_task
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import (MessageType, TextMessageEventContent, Format, RoomID)
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from mautrix.util.async_db import UpgradeTable, Connection
from mautrix.client import MembershipEventDispatcher
from typing import Type
import socket
import requests
from urllib.parse import urlparse
import http.client
import re

upgrade_table = UpgradeTable()

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE services (
            user TEXT,
            room TEXT PRIMARY KEY,
            web TEXT,
            noweb TEXT,
            time INTEGER NOT NULL,
            auto TEXT
        )"""
    )

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE allowed_users (
            user   TEXT PRIMARY KEY,
            time INTEGER NOT NULL,
            authenticator TEXT
        )"""
    )


class Config(BaseProxyConfig):
  def do_update(self, helper: ConfigUpdateHelper) -> None:
    helper.copy("rooms")
    helper.copy("message")
    helper.copy("notification_room")


class StatusBot(Plugin):

  async def start(self) -> None:
    await super().start()
    self.config.load_and_update()
    self.client.add_dispatcher(MembershipEventDispatcher)
    self._poll_task = background_task.create(self.poll())

  async def stop(self) -> None:
    self._poll_task.cancel()

  async def poll(self) -> None:
    while True:
      await asyncio.sleep(900)
      q = "SELECT user, room, web, noweb, time, auto FROM services"
      rows = await self.database.fetch(q)

      for row in rows:
        if row["auto"] == "True" or row["auto"] == "Fail":
          q = """
            INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (room) DO UPDATE SET auto=excluded.auto
            """
          ping_results = await self._ping(row["web"], row["noweb"])
          for i in ping_results[1]:
            content = TextMessageEventContent(
              msgtype=MessageType.TEXT, format=Format.HTML,
              body=f"Warning: Some of your services failed!",
              formatted_body=f"{i}")
            await self.client.send_message(row["room"], content)
          
          if ping_results[2] == "False" and row["auto"] == "True":
            await self.database.execute(q, row["user"], row["room"], row["web"], row["noweb"], row["time"], "Fail")
          if ping_results[2] == "False" and row["auto"] == "Fail":
            await self.database.execute(q, row["user"], row["room"], row["web"], row["noweb"], row["time"], "False")
            content = TextMessageEventContent(
              msgtype=MessageType.TEXT, format=Format.HTML,
              body=f"Warning: auto ping was turned off",
              formatted_body=f"Because auto ping detected failures a second time, auto ping was turned off.\nYou can reactivate it with !status auto")
            await self.client.send_message(row["room"], content)
            

  async def check_authenticated(self, user: str, room: str):
    q = "SELECT user, time, authenticator FROM allowed_users WHERE LOWER(user)=LOWER($1)"
    row = await self.database.fetchrow(q, user)
    if row:
      return row
    else:
      return await self.database.fetchrow(q, room)

  async def check_admin(self, evt: MessageEvent):
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't have permission for this command."))
    else:
      return True
  async def check_syntax(self, evt: MessageEvent, service: str, port):
    try:
      int(port)
    except ValueError:
      await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="Incorrect syntax used."))
      return False
    if int(port) > 65535:
      await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="Incorrect syntax used."))
      return False
    if len(re.findall(":[0-9]+", service)) == 0:
      return True
    elif len(re.findall(":[0-9]+", service)) == 1 and re.findall(":[0-9]+", service)[0][1:] == port and len(re.findall("/.", service)) > 0:
      return True
    else:
      await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="Incorrect syntax used."))
      return False

  async def check_url(self, url: str):
    url = urlparse(url)
    conn = http.client.HTTPSConnection(url.netloc)
    conn.request('GET', url.path, body=None, headers={"Accept": "text/plain"})
    resp = conn.getresponse().status
    conn.close()
    if len(str(resp)) == 3 and int(str(resp)[0]) > 1 and int(str(resp)[0]) < 4: 
        return True
    else:
        return False

  async def _ping(self, web, noweb):
    results = [[], [], "True"] #0 = reachable, 1 = not reachable, 3 = auto
    if web != None:
      webform = [[x, int(y)] for x, y in zip(web.split(",")[0::2], web.split(",")[1::2])]
      for i in range(len(webform)):
        if len(re.findall(":[0-9]+", str(webform[i][0]))) == 1 and len(re.findall("/.", webform[i][0])) > 0:
          url = str(webform[i][0])
        elif len(re.findall(":[0-9]+", str(webform[i][0]))) == 0 and len(re.findall("/.", webform[i][0])) > 0:
          url = str(webform[i][0]).split("/",1)[0] + ":" + str(webform[i][1]) + "/" + str(webform[i][0]).split("/",1)[1]
        else:
          url = webform[i][0] + ":" + str(webform[i][1])
        tls = ""
        try:
          if await self.check_url("https://" + url) and str(webform[i][1]) != "80":
            respcode = requests.get("https://" + url).status_code
            tls = "🔒️ "
          else:
            respcode = requests.get("http://" + url).status_code
            tls = "🔓️ "
        except socket.gaierror:
          respcode = "Error - couldn't reach Website!"
        if str(respcode) == "200":
            results[0].append(str(url + " ✅" + "[" + tls + str(respcode) + "]"))
        else:
            results[1].append(str(url + " 🛑" + "[" + tls + str(respcode) + "]"))

      if noweb != None:
        nowebform = [[x, int(y)] for x, y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
        for i in range(len(nowebform)):
          sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sock.settimeout(3)
          result = sock.connect_ex((nowebform[i][0], int(nowebform[i][1])))
          if result == 0:
            results[0].append(str(nowebform[i][0] + ":" + str(nowebform[i][1]) + " ✅"))
          else:
            results[1].append(str(nowebform[i][0] + ":" + str(nowebform[i][1]) + " 🛑"))
    if len(results[1]) == 0:
      return results
    else:
      results[2] = "False"
      return results

  @command.new()
  async def status(self, evt: MessageEvent) -> None:
    pass

  @status.subcommand(help="send this command to (de)activate auto ping and notification on failure")
  async def auto(self, evt: MessageEvent) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      q = "SELECT user, room, web, noweb, time, auto FROM services WHERE (room)=($1)"
      row = await self.database.fetchrow(q, evt.room_id)
      if row:
        q = """
            INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (room) DO UPDATE SET user=excluded.user, time=excluded.time, auto=excluded.auto
            """
        if row["auto"] == "True":
          await self.database.execute(q, evt.sender, evt.room_id, row["web"], row["noweb"], evt.timestamp, "False")
          await evt.reply(f"Notification on failure [OFF].")
        elif row["auto"] == "Fail":
          await self.database.execute(q, evt.sender, evt.room_id, row["web"], row["noweb"], evt.timestamp, "True")
          await evt.reply(f"The last auto ping detected failing services. Status of auto option was reset to non failure state")
          await evt.reply(f"Notification on failure [ON].")
        else:
          await self.database.execute(q, evt.sender, evt.room_id, row["web"], row["noweb"], evt.timestamp, "True")
          await evt.reply(f"Notification on failure [ON].")
      else:
        await evt.reply(f"There are no services observed in this chat, cant switch the status of the 'auto' parameter.")
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))

  @status.subcommand(help="add a service to observe")
  @command.argument("service")
  @command.argument("port")
  async def addweb(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      if await self.check_syntax(evt, service, port) == False: return
      q = "SELECT user, room, web, noweb, auto FROM services WHERE (room)=($1)"
      row = await self.database.fetchrow(q, evt.room_id)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        q = """
            INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (room) DO UPDATE SET user=excluded.user, web=excluded.web, time=excluded.time
            """
        if web != None:
          webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
          if [service, int(port)] in webform:
            await evt.reply(f"Der Service ist bereits vorhanden.")
          else:
            web += "," + service + "," + port
            await self.database.execute(q, evt.sender, evt.room_id, web, noweb, evt.timestamp, row["auto"])
            await evt.reply(f"The service was added.")
        else:
          web = service + "," + port
          await self.database.execute(q, evt.sender, evt.room_id, web, noweb, evt.timestamp, row["auto"])
          await evt.reply(f"The service was added.")
      else:
        q = """
        INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
        """
        web = service + "," + port
        await self.database.execute(q, evt.sender, evt.room_id, web, None, evt.timestamp, "False")
        await evt.reply(f"The service was added.")
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))

  @status.subcommand(help="add a service to observe")
  @command.argument("service")
  @command.argument("port")
  async def addnoweb(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      if await self.check_syntax(evt, service, port) == False: return
      q = "SELECT user, room, web, noweb, auto FROM services WHERE (room)=($1)"
      row = await self.database.fetchrow(q, evt.room_id)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        q = """
            INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (room) DO UPDATE SET user=excluded.user, noweb=excluded.noweb, time=excluded.time
            """
        if noweb != None:
          nowebform = [[x,int(y)] for x,y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
          if [service, int(port)] in nowebform:
            await evt.reply(f"Der Service {service}:{port} ist bereits vorhanden.")
          else:
            noweb += "," + service + "," + port
            await self.database.execute(q, evt.sender, evt.room_id, web, noweb, evt.timestamp, row["auto"])
            await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
        else:
          noweb = service + "," + port
          await self.database.execute(q, evt.sender, evt.room_id, web, noweb, evt.timestamp, row["auto"])
          await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
      else:
        q = """
        INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
        """
        noweb = service + "," + port
        await self.database.execute(q, evt.sender, evt.room_id, None, noweb, evt.timestamp, "False")
        await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))


  @status.subcommand(help="remove a service from observation")
  @command.argument("service")
  @command.argument("port")
  async def rem(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      if await self.check_syntax(evt, service, port) == False: return

      q = "SELECT user, room, web, noweb, auto FROM services WHERE (room)=($1)"
      row = await self.database.fetchrow(q, evt.room_id)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        removed = False
        if web != None:
          webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
          if [service, int(port)] in webform:
            webform.remove([service, int(port)])
            if len(webform) == 0:
              web = None
            else:
              web = ''.join([str(row[x]) + "," for row in webform for x in range(len(row))])[:-1]
            removed = True
        if noweb != None:
          nowebform = [[x,int(y)] for x,y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
          if [service, int(port)] in nowebform:
            nowebform.remove([service, int(port)])
            if len(nowebform) == 0:
              noweb = None
            else:
              noweb = ''.join([str(row[x]) + "," for row in nowebform for x in range(len(row))])[:-1]
            removed = True
        q = """
            INSERT INTO services (user, room, web, noweb, time, auto) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (room) DO UPDATE SET user=excluded.user, web=excluded.web, noweb=excluded.noweb, time=excluded.time
            """
        if removed == True:
          await self.database.execute(q, evt.sender, evt.room_id, web, noweb, evt.timestamp, row["auto"])
          await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="The Service was removed."))
        else:
          await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't observe this service, nothing was removed."))
      else:
        await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't observe any services"))
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))


  @status.subcommand(help="List your services")
  async def list(self, evt: MessageEvent) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      q = "SELECT user, room, web, noweb, time FROM services WHERE (room)=($1)"
      rows = await self.database.fetch(q, evt.room_id)
      if len(rows) == 0:
        await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="No services stored in database :("))
      else:
        observations = 0
        if rows[0]["web"] == None:
          formated_data = "\nwebservices:\n0"
        else:
          formated_data = "\nwebservices:"
          web = rows[0]["web"]
          webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
          observations += len(webform)
          formated_data += " ".join(f"\n{web}" for web in webform)

        if rows[0]["noweb"] == None:
          formated_data += "\nservices:\n0"
        else:
          formated_data += "\nservices:"
          noweb = rows[0]["noweb"]
          nowebform = [[x,int(y)] for x,y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
          observations += len(nowebform)
          formated_data += " ".join(f"\n{noweb}" for noweb in nowebform)
        await evt.reply(f"You observe {observations} services:\n\n```{formated_data}")
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))

  @status.subcommand(help="ping every service")
  async def ping(self, evt: MessageEvent) -> None:
    if await self.check_authenticated(evt.sender, evt.room_id):
      q = "SELECT user, room, web, noweb FROM services WHERE (room)=($1)"
      row = await self.database.fetchrow(q, evt.room_id)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        ping_results = await self._ping(web, noweb)
        for i in ping_results[0]:
          content = TextMessageEventContent(
            msgtype=MessageType.TEXT, format=Format.HTML,
            body=f"Ping results",
            formatted_body=f"{i}")
          await self.client.send_message(row["room"], content)
        for i in ping_results[1]:
          content = TextMessageEventContent(
            msgtype=MessageType.TEXT, format=Format.HTML,
            body=f"Ping results",
            formatted_body=f"{i}")
          await self.client.send_message(row["room"], content)          
      else:
        await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't observe any services"))
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Your user ID: " + str(evt.sender) + " was logged."))

  @command.new()
  async def admin(self, evt: MessageEvent) -> None:
    pass

  @admin.subcommand(help="authorize a person or a whole group to use the bot")
  @command.argument("user", pass_raw=True)
  async def authorize(self, evt: MessageEvent, user: str) -> None:
    if await self.check_admin(evt):
      q = """
          INSERT INTO allowed_users (user, time, authenticator) VALUES ($1, $2, $3)
          ON CONFLICT (user) DO UPDATE SET time=excluded.time, authenticator=excluded.authenticator
      """
      await self.database.execute(q, user, evt.timestamp, evt.sender)
      if str(user)[0] == "!":
        await evt.reply(f"Members of group [{user}] can now use the bot")
      else:  
        await evt.reply(f"{user} can now use the bot")

  @admin.subcommand(help="deauthorize a person or a whole group to use the bot")
  @command.argument("user", pass_raw=True)
  async def deauthorize(self, evt: MessageEvent, user: str) -> None:
    if await self.check_admin(evt):
      q = "DELETE FROM allowed_users WHERE LOWER(user)=LOWER($1)"
      await self.database.execute(q, user)
      if str(user)[0] == "!":
        await evt.reply(f"Members of group [{user}] can't use the bot anymore")
      else:
        await evt.reply(f"{user} can't use the bot anymore")

  @admin.subcommand(help="Get a specific allowed user")
  @command.argument("user")
  async def get(self, evt: MessageEvent, user: str) -> None:
    if await self.check_admin(evt):
      q = "SELECT user, time, authenticator FROM allowed_users WHERE user=$1"
      row = await self.database.fetchrow(q, user)
      if row:
        user = row["user"]
        time = row["time"]
        authenticator = row["authenticator"]
        await evt.reply(f"[✅]User: `{user}` stored by {authenticator} at `{time}`")
      else:
        await evt.reply(f"User: `{user}` not found!")

  @admin.subcommand(help="List authorized users")
  async def list(self, evt: MessageEvent) -> None:
    if await self.check_admin(evt):
      q = "SELECT user, time, authenticator FROM allowed_users"
      rows = await self.database.fetch(q)
      if len(rows) == 0:
          await evt.reply(f"Nothing stored in database :(")
      else:
          formatted_data = "\n".join(
              f"* `{row['user']}` stored by {row['authenticator']} at `{row['time']}`" for row in rows
          )
          await evt.reply(
              f"{len(rows)} accounts are allowed to use this bot:\n\n{formatted_data}"
          )

  @classmethod
  def get_db_upgrade_table(cls) -> UpgradeTable | None:
      return upgrade_table

  @classmethod
  def get_config_class(cls) -> Type[BaseProxyConfig]:
    return Config