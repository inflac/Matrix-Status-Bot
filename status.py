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

upgrade_table = UpgradeTable()

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE services (
            user   TEXT PRIMARY KEY,
            web TEXT NOT NULL,
            noweb TEXT NOT NULL,
            time TEXT NOT NULL
        )"""
    )

@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE allowed_users (
            user   TEXT PRIMARY KEY,
            time TEXT NOT NULL
        )"""
    )

@upgrade_table.register(description="Remember user who added value")
async def upgrade_v2(conn: Connection) -> None:
    await conn.execute("ALTER TABLE allowed_users ADD COLUMN authenticator TEXT")



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

  @command.new()
  async def status(self, evt: MessageEvent) -> None:
    pass

  @status.subcommand(help="add a service to observe")
  @command.argument("service")
  @command.argument("port")
  async def addweb(self, evt: MessageEvent, service: str, port: str) -> None:
    q = "SELECT user, time, authenticator FROM allowed_users WHERE LOWER(user)=LOWER($1)"
    row = await self.database.fetchrow(q, evt.sender)
    if row:
      q = "SELECT user, web, noweb FROM services WHERE LOWER(user)=LOWER($1)"
      row_web = await self.database.fetchrow(q, evt.sender)
      if row_web:
        user = row_web["user"]
        web = row_web["web"]
        noweb = row_web["noweb"]
        webform = [[x,int(y)] for x,y in zip(web.split(",")[0::2], web.split(",")[1::2])]
        if [service, int(port)] in webform:
          await evt.reply(f"Der Service {service}:{port} ist bereits vorhanden.")
        else:
          q = """
          INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
          ON CONFLICT (user) DO UPDATE SET web=excluded.web, noweb=excluded.noweb, time=excluded.time
          """
          web += "," + service + "," + port
          await self.database.execute(q, evt.sender, web, noweb, evt.timestamp)
          await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")
      else:
        q = """
        INSERT INTO services (user, web, noweb, time) VALUES ($1, $2, $3, $4)
        """
        web = service + "," + port
        await self.database.execute(q, evt.sender, web, "", evt.timestamp)
        await evt.reply(f"Der Service {service}:{port} wurde hinzugefügt.")        
    else:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du darfst diesen Bot nicht benutzen."))

  @status.subcommand(help="remove a service from observation")
  @command.argument("message")
  async def rem(self, evt: MessageEvent, message: str) -> None:
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Die Adresse: " + str(message) + " wurde entfernt."))

  @status.subcommand(help="ping every service")
  async def ping(self, evt: MessageEvent) -> None:
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen um Abfragen mit diesem Bot durchzuführen"))
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
  @command.argument("prefix", required=False)
  async def list(self, evt: MessageEvent, prefix: str | None) -> None:
    if evt.room_id not in self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen für diesen Befehl"))
    else:
      q = "SELECT user, time, authenticator FROM allowed_users WHERE user LIKE $1"
      rows = await self.database.fetch(q, prefix + "%")
      prefix_reply = f" starting with `{prefix}`" if prefix else ""
      if len(rows) == 0:
          await evt.reply(f"Nothing{prefix_reply} stored in database :(")
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