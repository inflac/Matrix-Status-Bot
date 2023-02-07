# Matrix-Status-Bot
A Matrix Bot that informs you about the current status of your services

## Setup
Create a file, named base-config.yaml and add your information as formated below.
<pre><code>allowed:
  [["@user:matrix.server.de"], ["RoomID:server02.de"]]
server:
  [["google.com",[21,22,25], [8080]],
  ["www.mozilla.org", [], [443]],
  ["github.com", [], [443]]]
</code></pre>
