from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import (MessageType, TextMessageEventContent)
from config import allowed,server
import socket
import requests
import hashlib
import string
import secrets


class StatusBot(Plugin):
  @command.new("help")
  async def help(self, evt: MessageEvent) -> None:
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Hallo " + str(evt.sender))
    await evt.reply(content)
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Dieser Bot erlaubt es authorisierten Personen den Status verschiedener Dienste abzufragen.")
    await evt.respond(content)
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Eine Abfrage kannst du mit dem Befehl !ping durchführen.")
    await evt.respond(content)
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="🛑Achtung: Solltest du unauthorisiert sein, wird deine BenutzerID an die Betreiber übermittelt🛑")
    await evt.respond(content)



  @command.new("authorize")
  async def authorize(self, evt: MessageEvent) -> None:
    user = evt.content[9::]
    sender = evt.sender
    room_id = evt.room_id
    timestamp = evt.timestamp

    salt1 = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(30))
    mac = (hashlib.sha256((user + sender + salt1 + room_id + timestamp).encode("utf-8")).hexdigest())
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Deine Kryptografischen Parameter lauten: Mac= " + str(mac) + "Salt= " + str(salt1))
    await evt.respond(content)

  @command.new("add")
  @command.argument("message")
  async def add(self, evt: MessageEvent, message:str) -> None:
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Die Adresse: " + str(message) + " wurde hinzugefügt.")
    await evt.respond(content)

  @command.new("add2")
  async def add2(self, evt: MessageEvent) -> None:
    await evt.reply("Die Adresse: " + str(evt.content[4::]) + " wurde hinzugefügt.")

  @command.new("add3")
  async def add3(self, evt: MessageEvent) -> None:
    message = str(evt.content[4::])
    await evt.respond("Die Adresse: " + str(message) + " wurde hinzugefügt.")

  @command.new("rem")
  async def rem(self, evt: MessageEvent) -> None:
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Die Adresse: " + str(evt.content[4::]) + " wurde entfernt.")
    await evt.respond(content)


  @command.new("ping")
  async def ping(self, evt: MessageEvent) -> None:

    if evt.room_id != allowed[1] or evt.sender not in allowed[0]:
        content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Du hast keine Berechtigungen um Abfragen mit diesem Bot durchzuführen")
        await evt.respond(content)
        content = TextMessageEventContent(msgtype=MessageType.TEXT, body="Deine Benutzer-ID lautet: " + str(evt.sender) + ".")
        await evt.respond(content)
    else:

        for i in range(len(server)):
            hostname = server[i][0]
            port_noweb = server[i][1]
            port_web = server[i][2]

            
            for j in range(len(port_noweb)):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((hostname, port_noweb[j]))
            
                if result == 0:
                    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_noweb[j]) + " ✅"))
                else:
                    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_noweb[j]) + " 🛑"))
                await evt.respond(content)


            for k in range(len(port_web)):
                respcode = requests.get("https://" + hostname + ":" + str(port_web[k]))
                if str(respcode) == "<Response [200]>":
                    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_web[k]) + " ✅"))
                else:
                    content = TextMessageEventContent(msgtype=MessageType.TEXT, body=str(hostname + ":" + str(port_web[k]) + " 🛑"))
                await evt.respond(content)