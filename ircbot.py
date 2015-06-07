#! /usr/bin/env python
# -*- coding: utf8 -*-

import irc.bot
import irc.strings
import os
import glob
import json
import time
import urllib2
import re
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr

TWITCH_URL = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance"
HITBOX_URL = "https://www.hitbox.tv/api/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"

class IgnoreErrorsBuffer(irc.buffer.DecodingLineBuffer):
    def handle_exception(self):
        pass

def read_from_file(path):
    try:
        content = ""
        with open(os.path.expanduser(path), 'r') as f:
            content = f.read().replace('\n', '')
        return content
    except:
        print "Need %s file" % path

def yt_id(url):
    yt_match = re.match(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)(watch\?v=|embed/|v/|.+v=|/)?([^&=%\?]{11})', url)
    
    if yt_match:
        return yt_match.group(6)

    return None

FAF_IRC_KEY = read_from_file('~/.faf_irc_key')
YOUTUBE_API_KEY = read_from_file('~/.youtube_api_key')

class Bot(irc.bot.SingleServerIRCBot):
    def __init__(self):
        irc.client.ServerConnection.buffer_class = irc.client.LineBuffer
        irc.bot.SingleServerIRCBot.__init__(self, [("irc.faforever.com", 6667)], "testacc99", "justabot")
    	self.chan = "#aeolus"
        self.lasttime = time.time() - 10 * 60
        self.lastreddit = time.time() - 10 * 60
        self.lastyt = time.time() - 1 * 60
        self.lastwhois = time.time() - 1 * 60
        
        self.lastmeow = time.time() - 10 * 60 * 60

    def on_welcome(self, c, e):
        self.log("got welcomed")
    
    def on_privnotice(self, c, e):
        print e.arguments
        if e.source.nick.lower() == "nickserv":
            if "IDENTIFY" in e.arguments[0]:
                c.privmsg("nickserv", "identify testacc99 %s" % FAF_IRC_KEY)
                self.log("identify")
            elif "recognized" in e.arguments[0]:
                c.join(self.chan)
                self.log("logged in")

    def on_pubmsg(self, c, e):
        try:
            self.handle_pubmsg(c, e)
        except Exception as ex:
            self.log(ex, "err")
        
    def handle_pubmsg(self, c, e):
        message = e.arguments[0]
        nick = e.source.split("!")[0]

        if time.time() - self.lastyt > 1 * 60:
            for msg_part in message.split():
                id = yt_id(msg_part)
                if id:
                    _url = "https://www.googleapis.com/youtube/v3/videos?id=%s&key=%s&fields=items(id,snippet(title),statistics(viewCount,likeCount,commentCount),contentDetails(duration))&part=snippet,statistics,contentDetails" % (id, YOUTUBE_API_KEY)
                    _data = json.loads(urllib2.urlopen(_url).read())
                    try:
                        vid = _data['items'][0]
                    except:
                        self.log(("no such yt id: %s, request by %s" % (id, nick)), "err")
                        return
                    self.lastyt = time.time()
                    self.log("youtube info requested by %s" % nick, "info")
                    c.action(self.chan, ("youtu.be/%s - %s [%s] - views: %s, likes: %s, comments: %s" % (vid['id'], vid['snippet']['title'], re.sub('[PT]', '' ,vid['contentDetails']['duration']).lower(), vid['statistics']['viewCount'], vid['statistics']['likeCount'], vid['statistics']['commentCount'])))
                    return

        if len(message) <= 1 or message[0] != "!":
            return
    
        cmd = message.split()[0][1:]

        if cmd == "streams" and not self.fafbot_online() and time.time() - self.lasttime > 10 * 60 and time.time() - self.lastyt > 1 * 60 and time.time() - self.lastreddit > 1 * 60:
            self.log("streams requested by %s" % nick, "info")
            self.lasttime = time.time()
            self.lastyt = time.time()
            streams = []
            try:
                streams_twitch = json.loads(urllib2.urlopen(TWITCH_URL).read())
                for stream in streams_twitch["streams"]:
                    streams.append({"channel": stream["channel"]["display_name"], "status": stream["channel"]["status"], "url": stream["channel"]["url"], "viewers": stream["viewers"]})
            except Exception as ex:
                pass

            try:
                streams_hitbox = json.loads(urllib2.urlopen(HITBOX_URL).read())
                for stream in streams_hitbox["livestream"]:
                    streams.append({"channel": stream["media_display_name"], "status": stream["media_status"], "url": stream["channel"]["channel_link"],  "viewers": int(stream["media_views"])})
            except Exception as ex:
                pass

            if len(streams) > 0:
                c.action(self.chan, ": %d streams online%s:" % (len(streams), " (top 3) " if len(streams) > 3 else ""))
                for i, stream in enumerate(sorted(streams, key=lambda s: s["viewers"], reverse=True)):
                    if i >= 3:
                        break
                    c.action(self.chan, (": %s - %s - %s (%s viewers)" % (stream["channel"], stream["status"], stream["url"], stream["viewers"])).replace('\r', ' ').replace('\n', ' '))
            else:
                c.action(self.chan, ": no streams :(")

        elif cmd == "casts" and not self.fafbot_online() and time.time() - self.lastreddit > 10 * 60 and time.time() - self.lasttime > 1 * 60:
            self.log("casts requested by %s" % nick, "info")
            try:
                reddit_url = "https://www.reddit.com/r/vids_of_faf/new.json?limit=3"
                reddit_resp = json.loads(urllib2.urlopen(urllib2.Request(reddit_url, headers={ 'User-Agent': 'listing casts for faforever.com 0.1'})).read())
            except:
                c.action(self.chan, "something bad happened, try again later")
                return
            
            for item in reddit_resp['data']['children']:
                try:
                    cast = item['data']['media']['oembed']
                    c.action(self.chan, (": %s - %s - %s") % (cast['author_name'], cast['title'], cast['url']))
                    continue
                except:
                    pass
                c.action(self.chan, (": %s - %s - %s") % (item['data']['author'], item['data']['title'], item['data']['url']))
            self.lastreddit = time.time()
        elif cmd == "cats" and time.time() - self.lastmeow > 10 * 60 *60:
            self.lastmeow = time.time()
            c.action(self.chan, "meow-meow http://youtu.be/SbyZDq76T74")
            self.log("meow by %s" % nick, "info")
        elif cmd == "whois" and len(message.split()) == 2 and time.time() - self.lastwhois > 1 * 60:
            url = "http://app.faforever.com/faf/userName.php"
            _faflogin = message.split()[1]
            if not re.match("^[\w_-]*$", _faflogin):
                return
            _html = urllib2.urlopen(url, "name=%s" % _faflogin).read()
            self.log("whois by %s" % nick, "info")
            _names = re.findall("<tr><td>([\w_-]*)</td><td>" , _html)
            if len(_names) == 0:
                if _html.find("didn't change his name") != -1:
                    return
                else:
                    _usedby = re.findall("<br /><b>([\w_-]*)</b>", _html)
                    if len(_usedby) > 0:
                        self.lastwhois = time.time()
                        c.action(self.chan, "%s was used by %s before" % (_faflogin, ", ".join(_usedby)))
            else:
                _prev_names = _names[-4:-1]
                self.lastwhois = time.time()
                c.action(self.chan, "%s was %s%s before" % (_faflogin, ", ".join(reversed(_prev_names)), ", .. (%s more)" % str(len(_names) - len(_prev_names)) if len(_names) - len(_prev_names) > 0 else "" ))

    def fafbot_online(self):
        for chan_name, chan_obj in self.channels.items():
            for user in chan_obj.users():
                if user == "fafbot":
                    return True
        return False

    def log(self, msg, level=None):
#        level = None
        colors = { "info": "\033[92m", "warn": "\033[93m", "err": "\033[91m" }
        print "%s[%s] %s%s" % (colors[level] if level in colors else "", time.strftime("%Y-%m-%d %H:%M:%S"), msg, "\033[0m" if level in colors else "")

if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0"
    Bot().start()

