from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import (MessageType, TextMessageEventContent)
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from mautrix.client import Client, InternalEventType, MembershipEventDispatcher, SyncStream
from typing import Awaitable, Type, Optional, Tuple
import socket
import requests
import hashlib
import string
import secrets


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


  @command.new("help")
  async def help(self, evt: MessageEvent) -> None:
    await evt.reply(TextMessageEventContent(msgtype=MessageType.TEXT, body="Hallo " + str(evt.sender)))
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Dieser Bot erlaubt es authorisierten Personen den Status verschiedener Dienste abzufragen."))
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Eine Abfrage kannst du mit dem Befehl !ping durchführen."))
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="🛑Achtung: Solltest du unauthorisiert sein, wird deine BenutzerID an die Betreiber übermittelt🛑"))


  @command.new("authorize")
  @command.argument("user")
  async def authorize(self, evt: MessageEvent, user: str) -> None:
    sender = str(evt.sender)
    room_id = str(evt.room_id)
    timestamp = str(evt.timestamp)

    salt1 = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(30))
    mac = (hashlib.sha256((str(user) + sender + str(salt1) + room_id + timestamp).encode("utf-8")).hexdigest())
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Deine Kryptografischen Parameter lauten: Mac= " + str(mac) + " Salt= " + str(salt1)))


  @command.new("add")
  @command.argument("message")
  async def add(self, evt: MessageEvent, message: str) -> None:
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Die Adresse: " + str(message) + " wurde hinzugefügt."))


  @command.new("rem")
  @command.argument("message")
  async def rem(self, evt: MessageEvent, message: str) -> None:
    await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Die Adresse: " + str(message) + " wurde entfernt."))


  @command.new("ping")
  async def ping(self, evt: MessageEvent) -> None:
    if evt.room_id != self.config["allowed"][1] or evt.sender not in self.config["allowed"][0]:
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen um Abfragen mit diesem Bot durchzuführen"))
      await evt.respond(TextMessageEventContent(msgtype=MessageType.TEXT, body="Deine Benutzer-ID lautet: " + str(evt.sender) + "."))
    else:
      for i in range(len(self.config["server"])):
        hostname = self.config["server"][i][0]
        port_noweb = self.config["server"][i][1]
        port_web = self.config["server"][i][2]
        self.log.debug(f"hostname: `{hostname}` port_noweb {port_noweb} port_web {port_web}")

        for j in range(len(port_noweb)):
          sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sock.settimeout(3)
          result = sock.connect_ex((hostname, port_noweb[j]))
          self.log.debug(f"result: `{result}`")
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

  @classmethod
  def get_config_class(cls) -> Type[BaseProxyConfig]:
    return Config