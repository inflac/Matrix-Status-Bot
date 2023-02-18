from __future__ import annotations
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import (MessageType, TextMessageEventContent)
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from mautrix.util.async_db import UpgradeTable, Connection
from mautrix.client import MembershipEventDispatcher
from typing import Type
import socket
import requests
import re

upgrade_table = UpgradeTable()

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE services (
            user   TEXT PRIMARY KEY,
            web TEXT,
            noweb TEXT,
            time INTEGER NOT NULL
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

  async def check_authenticated(self, user: str):
    q = "SELECT user, time, authenticator FROM allowed_users WHERE LOWER(user)=LOWER($1)"
    return await self.database.fetchrow(q, user)

  async def check_syntax(self, evt: MessageEvent, port: str):
    try:
      int(port)
    except ValueError:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Incorrect syntax used."))
      return False
    return True

  @command.new()
  async def status(self, evt: MessageEvent) -> None:
    pass

  @status.subcommand(help="add a service to observe")
  @command.argument("service")
  @command.argument("port")
  async def addweb(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender): 
      if await self.check_syntax(evt, port) == False: return
      
      q = "SELECT user, web, noweb FROM services WHERE LOWER(user)=LOWER($1)"
      row = await self.database.fetchrow(q, evt.sender)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        q = """
            INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
            ON CONFLICT (user) DO UPDATE SET web=excluded.web, time=excluded.time
            """
        if web != None:
          webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
          if [service, int(port)] in webform:
            await evt.reply(f"Der Service {service}:{port} ist bereits vorhanden.")
          else:
            web += "," + service + "," + port
            await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
            await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
        else:
          web = service + "," + port
          await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
          await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
      else:
        q = """
        INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
        """
        web = service + "," + port
        await self.database.execute(q, evt.sender, web, None, evt.timestamp)
        await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")        
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))

  @status.subcommand(help="add a service to observe")
  @command.argument("service")
  @command.argument("port")
  async def addnoweb(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender):
      if await self.check_syntax(evt, port) == False: return

      q = "SELECT user, web, noweb FROM services WHERE LOWER(user)=LOWER($1)"
      row = await self.database.fetchrow(q, evt.sender)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        q = """
            INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
            ON CONFLICT (user) DO UPDATE SET noweb=excluded.noweb, time=excluded.time
            """
        if noweb != None:
          nowebform = [[x,int(y)] for x,y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
          if [service, int(port)] in nowebform:
            await evt.reply(f"Der Service {service}:{port} ist bereits vorhanden.")
          else:
            noweb += "," + service + "," + port
            await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
            await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
        else:
          noweb = service + "," + port
          await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
          await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
      else:
        q = """
        INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
        """
        noweb = service + "," + port
        await self.database.execute(q, evt.sender, None, noweb, evt.timestamp)
        await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")        
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))


  @status.subcommand(help="remove a service from observation")
  @command.argument("service")
  @command.argument("port")
  async def rem(self, evt: MessageEvent, service: str, port: str) -> None:
    if await self.check_authenticated(evt.sender):
      if await self.check_syntax(evt, port) == False: return

      q = "SELECT user, web, noweb FROM services WHERE LOWER(user)=LOWER($1)"
      row = await self.database.fetchrow(q, evt.sender)
      if row:
        web = row["web"]
        noweb = row["noweb"]
        removed = False
        if web != None:
          webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
          if [service, int(port)] in webform:
            self.log.info(web)
            webform.remove([service, int(port)])
            web = ''.join([str(row[x]) + "," for row in webform for x in range(len(row))])[:-1]
            self.log.info(web) 
            removed = True
        if noweb != None:
          nowebform = [[x,int(y)] for x,y in zip(noweb.split(",")[0::2], noweb.split(",")[1::2])]
          if [service, int(port)] in nowebform:
            self.log.info(noweb) 
            nowebform.remove([service, int(port)])
            noweb = ''.join([str(row[x]) + "," for row in nowebform for x in range(len(row))])[:-1]
            self.log.info(noweb)
            removed = True
        q = """
            INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
            ON CONFLICT (user) DO UPDATE SET web=excluded.web, noweb=excluded.noweb, time=excluded.time
            """
        if removed == True:
          await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
          await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="The Service was removed."))
        else:
          await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't observe this service, nothing was removed."))
      else:
        await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You don't observe any services"))
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))
            

  @status.subcommand(help="List your services")
  async def list(self, evt: MessageEvent) -> None:
    if await self.check_authenticated(evt.sender):
      q = "SELECT user, web, noweb, time FROM services WHERE user = $1"
      rows = await self.database.fetch(q, evt.sender)
      if len(rows) == 0:
        await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="No services stored in database :("))
      
      observations = 0
      formated_data = "\nwebservices:"
      web = rows[0]["web"]
      webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
      observations += len(webform)
      formated_data += " ".join(f"\n{web}" for web in webform)
      
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
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="You aren't allowed to use this bot."))
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Deine Benutzer-ID lautet: " + str(evt.sender) + "."))
    else:
      for i in range(len(self.config["server"])):
        hostname = self.config["server"][i][0]
        port_noweb = self.config["server"][i][1]
        port_web = self.config["server"][i][2]

        for j in range(len(port_noweb)):
          sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sock.settimeout(3)
          result = sock.connect_ex((hostname, port_noweb[j]))
          if result == 0:
            await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_noweb[j]) + " ✅")))
          else:
            await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_noweb[j]) + " 🛑")))

        for k in range(len(port_web)):
          respcode = requests.get("https://" + hostname + ":" + str(port_web[k]))
          if str(respcode) == "<Response [200]>":
            await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_web[k]) + " ✅")))
          else:
            await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_web[k]) + " 🛑")))


  @command.new()
  async def admin(self, evt: MessageEvent) -> None:
    pass

  @admin.subcommand(help="authorize a person to use the status bot")
  @command.argument("user", pass_raw=True)
  async def authorize(self, evt: MessageEvent, user: str) -> None:
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen für diesen Befehl"))
    else:
      q = """
          INSERT INTO allowed_users (user, time, authenticator) VALUES ($1, $2, $3)
          ON CONFLICT (user) DO UPDATE SET time=excluded.time, authenticator=excluded.authenticator
      """
      await self.database.execute(q, user, evt.timestamp, evt.sender)
      await evt.reply(f"{user} kann den Bot nun verwenden")

  @admin.subcommand(help="deauthorize a person to use the bot")
  @command.argument("user", pass_raw=True)
  async def deauthorize(self, evt: MessageEvent, user: str) -> None:
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen für diesen Befehl"))
    else:
      q = "DELETE FROM allowed_users WHERE LOWER(user)=LOWER($1)"
      await self.database.execute(q, user)
      await evt.reply(f"{user} kann den Bot nun nicht mehr verwenden")
    
  @admin.subcommand(help="Get a specific allowed user")
  @command.argument("user")
  async def get(self, evt: MessageEvent, user: str) -> None:
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen für diesen Befehl"))
    else:
      q = "SELECT user, time, authenticator FROM allowed_users WHERE LOWER(user)=LOWER($1)"
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
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen für diesen Befehl"))
    else:
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