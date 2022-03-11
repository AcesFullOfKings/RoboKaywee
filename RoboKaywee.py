#import sqlite3 # LOL JK, but maybe one day I'll use an actual database 
import os
import re
import praw # takes 0.33s to import!
import prawcore.exceptions
import random
import requests
import subprocess

import math as maths # correct the typo in the standard library. fucking americans

from os          import getcwd
from time        import time, sleep, localtime
from enum        import IntEnum
from math        import ceil
from james       import timeuntil # takes 0.4s to import!
from string      import ascii_lowercase, printable
from shutil      import copy2 as copy_with_metadata # who the fuck calls something "copy2"? Get your shit together Python Foundation, damn. BuT iTs ThE sEcOnD vErSiOn oF CoPy, gtfo
from chatbot     import ChatBot # see https://github.com/theonefoster/pyTwitchChatBot
from datetime    import date, datetime
from threading   import Thread, Lock, Event
from contextlib  import suppress
from credentials import bot_name, password, channel_name, kaywee_channel_id, robokaywee_client_id, tof_channel_id, robokaywee_secret

import commands as commands_file # takes 0.3s to import!
from API_functions import get_app_access_token, get_name_from_user_ID, get_followers

"""
TODO:
should be able to give any command multiple names via aliases
"""

try: # try to name the window
	import ctypes
	ctypes.windll.kernel32.SetConsoleTitleW("RoboKaywee")
	del ctypes
except: # might not work on linux / etc.. oh well
	pass

def log(s):
	"""
	Takes a string, s, and logs it to a log file on disk with a timestamp. Also prints the string to console.
	"""
	current_time = localtime()
	# year   = str(current_time.tm_year)
	month  = str(current_time.tm_mon ).zfill(2)
	day    = str(current_time.tm_mday).zfill(2)
	hour   = str(current_time.tm_hour).zfill(2)
	minute = str(current_time.tm_min ).zfill(2)
	second = str(current_time.tm_sec ).zfill(2)
	
	log_time = f"{day}/{month} {hour}:{minute}:{second}"

	print(f"{hour}:{minute} - {s}")
	with open("log.txt", "a", encoding="utf-8") as f:
		f.write(log_time + " - " + s + "\n")

def get_data(name, default=None):
	try:
		if config_lock.acquire(timeout=3):
			with open("config.txt", "r") as f:
				file = f.read()
				data = dict(eval(file))
				return data.get(name, default)
		else:
			log("WARNING: config_lock timed out in get_data() !!")
			return default
	except FileNotFoundError as ex:
		log(f"Failed to get data called {name} - File Not Found.")
	except ValueError as ex:
		log(f"Failed to get data called {name} - Value Error (corrupt file??)")
	except:
		log(f"Unknown error when reading data in get_data (trying to get {name})")
	finally:
		with suppress(RuntimeError):
			config_lock.release()

def set_data(name, value):
	try:
		if config_lock.acquire(timeout=3):
			with open("config.txt", "r") as f:
				file = f.read()
				data = dict(eval(file))
				data[name] = value
		else:
			log("WARNING: config_lock timed out (while reading) in set_data() !!")
			return
	except FileNotFoundError as ex:
		log(f"Failed to set data of {name} to {value} - File Not Found.")
		return
	except ValueError as ex:
		log(f"Failed to set data of {name} to {value} - Value Error (corrupt file?)")
		return
	except:
		log(f"Unknown error when reading data in set_data: trying to set {name} to {value}.")
	finally:
		with suppress(RuntimeError):
			config_lock.release()

	try:
		if config_lock.acquire(timeout=3):
			with open("config.txt", "w") as f:
				f.write(str(data)) #.replace(", ", "},\n")
			
			with suppress(RuntimeError):
				config_lock.release()
		else:
			log("WARNING: config_lock timed out (while writing) in set_data() !!")
			return
	except:
		log(f"Unknown error in set_data when setting data {name} to {value}.")
	finally:
		with suppress(RuntimeError):
			config_lock.release()

command_lock   = Lock()
config_lock    = Lock()
subs_lock      = Lock()
usernames_lock = Lock()
wiki_lock      = Lock()

channel_live        = Event()
channel_offline     = Event()
live_status_checked = Event()
live_status_checked.clear()

try:
	online_time = get_data("online_time")
	if online_time is not None:
		channel_live.set()
except Exception as ex:
	log("Exception reading online_time: " + str(ex))
	online_time = None

bots = {"robokaywee", "streamelements", "nightbot"}

bot = None
shutdown_on_offline = False # can be set to true to shutdown pc when streamer goes offline

twitch_emotes = [] # populated by get_twitch_emotes() below

# some regexes for detecting certain message patterns
ayy_re     = re.compile("a+y+") # one or more "a" followed by one or more "y", e.g. aayyyyy
hello_re   = re.compile("h+i+|h+e+y+|h+e+l+o+|h+o+l+a+|h+i+y+a+") # various ways of saying hello
patrick_re = re.compile("is this [^ ?]+\?*$") # "is this " followed by a word, followed by zero or more question marks. e.g. "is this kaywee??"
sheesh_re  = re.compile("s+h+e{2,}s+h+") # sheesh
aaa_re     = re.compile("a{4,}") # aaaa

# when only mods send messages into chat for at least `key` messages, the bot will announce the modwall.
# the Name is the type of modwall which gets announced into chat
# the emotes are what get appended to the announcement
# the excitement is the number of exclamation marks to use
# when a modwall is interrupted by a non-mod sending a message, the bot will announce the modwall breaking with the break_emotes
# a broken modwall will only be announced if the size is > modwall_break_level, defined below
modwalls = {
	15:  {"name": "Modwall",                 "emotes": "kaywee1AYAYA",                                                           "excitement": 1, "break_emotes": ":("},
	30:  {"name": "Supermodwall",            "emotes": "SeemsGood kaywee1Wut",                                                   "excitement": 1, "break_emotes": ":( FeelsBadMan"},
	60:  {"name": "MEGA MODWALL",            "emotes": "TwitchLit kaywee1AYAYA kaywee1Wut",                                      "excitement": 2, "break_emotes": ":( FeelsBadMan NotLikeThis"},
	120: {"name": "H Y P E R MODWALL",       "emotes": "kaywee1AYAYA PogChamp Kreygasm CurseLit",                                "excitement": 2, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands"},
	250: {"name": "U L T R A M O D W A L L", "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 3, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	500: {"name": "G I G A M O D W A L L",   "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 3, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	# I guarantee none of these will ever be reached naturally, but..
	1000:{"name": "PETAMODWALL",             "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 4, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	2000:{"name": "EXAMODWALL",              "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 5, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	3000:{"name": "ZETTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 6, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	4000:{"name": "YOTTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 7, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	# I know that the SI prefixes don't match the numbers, but whatever, I needed increasing prefixes
}

get_modwall = lambda x: modwalls[sorted(list(key for key in modwalls.keys() if key <= x))[-1]]
modwall_break_level = sorted(modwalls.keys())[1] # the second smallest modwall size

with open("usernames.txt", "r", encoding="utf-8") as f:
	usernames = set(f.read().split("\n"))

with open("commands.txt", "r", encoding="utf-8") as f:
	commands_dict = dict(eval(f.read()))

with open("subscribers.txt", "r", encoding="utf-8") as f:
	try:
		subscribers = dict(eval(f.read()))
	except Exception as ex:
		log("Exception creating subscriber dictionary: " + str(ex))
		subscribers = {}

with open("followers.txt", "r", encoding="utf-8") as f:
	try:
		followers = dict(eval(f.read()))
	except Exception as ex:
		log("Exception creating follower dictionary: " + str(ex))
		followers = {}

with open("titles.txt", "r", encoding="utf-8") as f:
	titles = f.read().split("\n")

def streamer_is_live():
	global authorisation_header, kaywee_channel_id

	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id

	try:
		# if this call succeeds, streamer is Live. Exceptions imply streamer is offline (as no stream title exists)
		title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
		return True

	# streamer is offline:
	except (IndexError, KeyError):
		return False

	except Exception as ex:
		log("Exception when checking if streamer is Live: " + str(ex))
		return False # assume offline if live status is unknown to avoid spamming chat

def channel_went_offline():
	global channel_live
	global channel_offline
	global online_time
	global shutdown_on_offline
	global live_status_checked

	if online_time is not None: # don't try to go offline when already offline
		# live_stats_checked is not set the first time this runs, i.e. when the bot is starting. 
		# don't send the message to chat if the channel is offline when the bot starts
		if live_status_checked.is_set():
			uptime = int(time() - online_time)

			hours = int((uptime % 86400) // 3600)
			mins  = int((uptime % 3600) // 60)
			# seconds = int (uptime % 60) # removed - uptime isn't precise enough to justify sending the seconds

			uptime_string = f"{channel_name} went offline. Uptime was approximately {hours} hours and {mins} mins."
			log(uptime_string)
			send_message(uptime_string)

		online_time = None
		set_data("online_time", None)

		# these should be the last thing the function does, as other threads may depend on these events
		channel_live.clear()
		channel_offline.set()

		# ...unless we shut down in which case it doesn't matter
		if shutdown_on_offline:
			log("Shutting down the PC..")
			sleep(1)
			subprocess.run("Shutdown /s /f")

def channel_came_online():
	global channel_live
	global channel_offline
	global online_time
	global bUrself_sent
	global ali_sent

	log(f"{channel_name} came online.")
	online_time = int(time()) # set first time seen online
	set_data("online_time", online_time)

	bUrself_sent = False
	set_data("bUrself_sent", False)
	ali_sent = False
	set_data("ali_sent", False)

	Thread(target=promote_socials, name="Socials").start()

	# these should be the last thing the function does, as other threads may depend on these events
	channel_offline.clear()
	channel_live.set()

def check_live_status():
	global channel_live
	
	if not streamer_is_live():
		if channel_live.is_set():
			channel_went_offline()
	else:
		# streamer is online:
		if not channel_live.is_set():
			channel_came_online()

		#add_seen_title(title) # save unique stream title

def channel_events():
	"""Checks live status regularly. If channel goes live or goes offline, global Thread events are triggered."""

	period = 120

	check_live_status()
	live_status_checked.set() # signal to other threads that first run is complete

	while True:
		sleep(period)
		
		try:
			check_live_status()
		except Exception as ex:
			log("Exception while checking Live Status: " + str(ex))
		
def play_patiently():
	reminder_period = 60*60
	last_patient_reminder = get_data("last_patient_reminder", 0)

	time_since = time() - last_patient_reminder
	if time_since <= reminder_period:
		wait_time = reminder_period - time_since
	else:
		wait_time = 0

	sleep(wait_time)

	while True:
		if streamer_is_live():
			send_message("@Kaywee - Reminder: play patiently!")
			log("Sent patient reminder.")
			set_data("last_patient_reminder", int(time()))
		else:
			channel_live.wait() # channel is offline.. wait to come back online

		sleep(reminder_period) # wait an hour before retrying

last_wiki_update = 0
def update_commands_wiki(force_update_reddit=False):
	global last_wiki_update
	global permissions

	if force_update_reddit or last_wiki_update < time() - 60*30: # don't update more often than 30 mins unless forced
		#permissions_dict = {0:"Pleb", 2:"Follower", 4:"Subscriber", 6:"VIP", 8:"Mod", 9:"Owner", 10:"Broadcaster", 20:"Disabled"}
		permissions_dict = {p.value : p.name for p in permissions}

		try:
			r = praw.Reddit("RoboKaywee") # log in to reddit API with RoboKaywee credentials
			subreddit = r.subreddit("RoboKaywee") # get /r/RoboKaywee subreddit object

			if command_lock.acquire(timeout=10):
				with open("commands.txt", "r", encoding="utf-8") as f:
					commands = dict(eval(f.read()))

				with suppress(RuntimeError):
					command_lock.release()

				table = ("" + # "**Note: most commands are sent with /me so will display in the bot's colour.**\n\n\n" + 
						"**Command**|**Level**|**Response/Description**|**Uses**\n---|---|---|---\n")

				for command in sorted(commands):
					if "permission" in commands[command]:
						try:
							level = permissions_dict[commands[command]["permission"]]
						except KeyError:
							level = "Pleb"
					else:
						level = "Pleb"

					if "uses" in commands[command]:
						uses = commands[command]["uses"]
					else:
						uses = "-"

					if commands[command]["coded"]:
						if "description" in commands[command]:
							description = commands[command]['description'].replace("|", "/") # pipes break the formatting on the reddit wiki
							table += f"{command}|{level}|Coded: {description}|{uses}\n"
						else:
							table += f"{command}|{level}|Coded command with no description.|{uses}\n"
					else:
						if "response" in commands[command]:
							response = commands[command]['response'].replace("|", "/") # pipes break the formatting on the reddit wiki
							table += f"{command}|{level}|Response: {response}|{uses}\n"
						else:
							table += f"{command}|{level}|Text command with no response.|{uses}\n"

				subreddit.wiki["commands"].edit(table) # send commands table to reddit
				last_wiki_update = time()
			else:
				log("Warning: Command Lock timed out on update_commands_wiki() !!")
		except prawcore.exceptions.ResponseException:
			log(f"Response exception received when writing to reddit wiki - is reddit down?")
		except Exception as ex:
			log(f"Exception when writing to reddit wiki: {str(ex)}")
		finally:
			with suppress(RuntimeError):
				command_lock.release()

def write_command_data(force_update_reddit=False):
	global commands_dict

	if command_lock.acquire(timeout=3):
		with open("commands.txt", "w", encoding="utf-8") as f:
			f.write(str(commands_dict).replace("},", "},\n"))
		
		with suppress(RuntimeError):
			command_lock.release()

		Thread(target=update_commands_wiki, args=(force_update_reddit,)).start()
	else:
		log("Warning: Command Lock timed out on write_command_data() !!")

def commit_subscribers():
	try:
		if command_lock.acquire(timeout=3):
			with open("subscribers.txt", "w", encoding="utf-8") as f:
				f.write(str(subscribers))
		else:
			log("Warning: Subs Lock timed out in commit_subscribers() !!")
	except Exception as ex:
		log("Exception in commit_subscribers: " + str(ex))
	finally:
		with suppress(RuntimeError):
			command_lock.release()

def add_new_username(username):
	send_message(f"Welcome to Kaywee's channel {username}! Get cosy and enjoy your stay {get_emote('kaywee1AYAYA')} <3")
	log(f"Welcomed new user {username}")

	global usernames	
	usernames.add(username)
	try:
		if usernames_lock.acquire(timeout=3):
			with open("usernames.txt", "w", encoding="utf-8") as f:
				f.write("\n".join(usernames))
		else:
			log(f"Failed to aquire usernames_lock after 3 seconds! {username} was not added to the text file.")
	except Exception as ex:
		log("Exception in add_new_username: " + str(ex))
	finally:
		with suppress(RuntimeError):
			usernames_lock.release()

def add_seen_title(title):
	global titles

	if title not in titles: # only unique titles
		titles.append(title)
		with open("titles.txt", "w", encoding="utf-8") as f:
			f.write("\n".join(titles))

def set_random_colour():
	days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	
	while True:
		today_name = days[date.today().weekday()]
		last_colour_change = get_data("lastcolourchange")
		
		if last_colour_change is None or last_colour_change != today_name:
			set_data("lastcolourchange", today_name)
			if today_name == "Wednesday":
				send_message("/color HotPink", False)
				set_data("current_colour", "HotPink")
				log(f"Colour was updated to HotPink in response to Timed Event")
			else:
				colours = ["blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","orangered","red","seagreen","springgreen","yellowgreen"]
				new_colour = random.choice(colours)
				send_message("/color " + new_colour, False)
				set_data("current_colour", new_colour)
				log(f"Colour was updated to {new_colour} in response to Timed Event")

		sleep(4*60*60) # 4 hours

def it_is_wednesday_my_dudes():
	reminder_period = 60*60
	last_pink_reminder = get_data("last_pink_reminder", 0)

	sleep(90) # always wait a bit bc otherwise it sends play patiently messages at the same time

	time_since = time() - last_pink_reminder
	if time_since <= reminder_period:
		wait_time = reminder_period - time_since
	else:
		wait_time = 0

	sleep(wait_time)

	while True:
		channel_live.wait() # if channel goes offline, wait for it to come back online
		if date.today().weekday() == 2 and datetime.now().hour >= 6: # if it's wednesday and it's not earlier than 6am
			send_message("On Wednesdays we wear pink. If you want to sit with us type /color HotPink to update your username colour.")
			log("Sent Pink reminder.")
			set_data("last_pink_reminder", int(time()))
		else:
			return # this thread will be recreated next wednesday by channel_live_messages
		sleep(reminder_period)

def it_is_thursday_my_dudes():
	sleep(20*60) # wait 20 mins into the stream
	send_message("On Thursdays we wear whatever colour we want. Set your username colour by using /color and sit with us.")
	log("Sent UnPink reminder.")

def it_is_worldday_my_dudes():
	sleep(10*60) # wait 10 mins into stream
	commands_file.worldday({"display-name":"Timed Event"}) # need to include a message dict param

def wordoftheday_timer():
	sleep(30*60) # wait 30 mins into stream
	commands_file.wordoftheday({"display-name":"Timed Event"}) # have to include a message dict param

def ow2_msgs():
	while True:
		channel_live.wait()
		sleep(random.randint(15*60, 45*60)) # random wait between 15 and 45 mins
		commands_file.ow2({"display-name": "Timed Event"})

def promote_socials(delay=60*180):
	sleep(delay)
	send_message("Kaywee is on Twitter/Insta! 🐦 http://kaywee.live/twitter // 📷 http://kaywee.live/ig")

def channel_live_messages():
	global channel_live
	global live_status_checked
	
	live_status_checked.wait() # wait for check_live_status to run once
	
	while True:
		if not channel_live.is_set():  # if channel isn't already live when bot starts
			channel_live.wait()        # wait for channel to go live
			send_message("!resetrecord")
			sleep(5)
			send_message("@kaywee - don't forget to enable/disable TreatStream (!treat)")

		weekday_num = date.today().weekday()
		if weekday_num == 3:
			daily_message_func = it_is_thursday_my_dudes
		elif weekday_num == 2:
			daily_message_func = it_is_wednesday_my_dudes
		else:
			daily_message_func = None # will cause a targetless thread to be created which will immediately terminate

		#Thread(target=it_is_worldday_my_dudes, name="Worldday Thread"    ).start() # waits 10m, sends message once, then exits
		Thread(target=daily_message_func,       name="DailyMessage Thread").start()   # waits 20m, sends message once, then exits
		#Thread(target=wordoftheday_timer,      name="WordOfTheDay Thread").start()  # waits 30m, sends message once, then exits

		channel_offline.wait() # wait for channel to go offline before running again

def nochat_raid(raider):
	try:
		sleep(10)
		send_message(f"@{raider} thank you so much for raiding! Kaywee isn't looking at chat right now (!nochat) but she'll see the raid after the current game.")
		log(f"Sent nochat to {raider} for raiding")
	except Exception as ex:
		log("Exception in nochat_raid: " + str(ex))

def update_subs():
	while True:
		for sub in list(subscribers):
			if subscribers[sub]["subscribe_time"] < time() - 60*60*24*30:
				del subscribers[sub]
		commit_subscribers()
		sleep(10*60)

def update_followers():
	global followers 
	global authorisation_header

	while True:
		sleep(10*60)
		channel_live.wait() # only bother polling while channel is live 

		url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id

		# first check total follow count from twitch:
		try:
			data = requests.get(url, headers=authorisation_header).json()
			follower_count = data["total"]
		except Exception as ex:
			log("Exception while requesting followers: " + str(ex))
			continue

		# only update followers if total follow count has changed: 
		# (this might mean e.g. one unfollowed and one followed so the count stayed the same but the list changed.. but oh well)
		if follower_count != len(followers):
			try:
				followers = get_followers() # occasionally causes the thread to crash so wrapped it in a try
			except Exception as ex:
				log("Exception getting followers: " + str(ex))
			else:
				try:
					with open("followers.txt", "w", encoding="utf-8") as f:
						f.write(str(followers))
				except Exception as ex:
					log("Exception writing followers: " + str(ex))
					followers = {} # should get updated on next loop

def automatic_backup():
	"""
	Autmatically makes a backup of all bot files once per week. Does not delete old files.
	"""
	
	backup_period  = 86400 * 7 # backup once per 7 days
	check_interval = 120*60    # check  once per 2 hours

	while True:
		if get_data("last_backup", 0) < time() - backup_period:
			today_dt = datetime.today()
			year = str(today_dt.year)[-2:]
			month = str(today_dt.month).zfill(2)
			day = str(today_dt.day).zfill(2)

			fdate = f"{year}.{month}.{day}"
			folder_name = getcwd() + f"\\backups\\Backup - {fdate}"

			if not os.path.exists(folder_name):
				os.mkdir(folder_name)

			for filename in os.listdir(getcwd()):
				if any(filename.endswith(ext) for ext in [".txt", ".py"]):
					full_src = getcwd()    + f"\\{filename}" # source file full path
					full_dst = folder_name + f"\\{filename}" # dest file full path
					copy_with_metadata(full_src, full_dst)

			set_data("last_backup", int(time()))

		sleep(check_interval)

def update_app_access_token(force_refresh=False):
	global authorisation_header
	url = "https://id.twitch.tv/oauth2/validate"

	while True:
		try:
			current_token = get_data("app_access_token", None)
			assert current_token is not None

			response = requests.get(url, headers=authorisation_header).json()
			expires_in = response["expires_in"]
		except AssertionError:
			log("No App Access Token was found in config.txt. Fetching a new one..")
			expires_in = 0
		except Exception as ex:
			log("Exception when checking App Access Token: " + str(ex) + " -- Fetching a new token..")
			expires_in = 0

		if expires_in < 48*60*60 or force_refresh: # if token expires in the next 48h
			new_token = get_app_access_token(log)
			print("New token is " + new_token)
			set_data("app_access_token", new_token) # get a new one
			authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + new_token}
			force_refresh = False

		sleep(23*60*60) # wait 23 hours

def send_message(message, add_to_chatlog=True): # , suppress_colour=True):
	"""
	Will also be accessible from the commands file.
	"""

	#if message[0] in "/." or suppress_colour:
	bot.send_message(message)
	#else:
	#	bot.send_message("/me " + message) # very sad that twitch got rid of this. Stupid twitch.

	if add_to_chatlog:
		with open("chatlog.txt", "a", encoding="utf-8") as f:
			f.write("robokaywee: " + message + "\n")

def check_cooldown(command_name, user):
	command_time = ceil(time())
	cmd_data = commands_dict[command_name]

	def check_user_cooldown():
		if "user_cooldown" in cmd_data:
			if user in user_cooldowns:
				if command_name in user_cooldowns[user]:
					if user_cooldowns[user][command_name] < command_time - cmd_data["user_cooldown"]:
						user_cooldowns[user][command_name] = command_time
						return True
					else:
						return False
				else:
					user_cooldowns[user][command_name] = command_time
					return True
			else:
				user_cooldowns[user] = {command_name:command_time}
				return True
		else:
			cmd_data["last_used"] = command_time
			return True

	if "global_cooldown" in cmd_data:
		if "last_used" in cmd_data:
			if cmd_data["last_used"] < command_time - cmd_data["global_cooldown"]:
				return check_user_cooldown()
			else:
				return False
		else:
			return check_user_cooldown()
	else:
		return check_user_cooldown()

def create_bot():
	global bot
	global commands_file

	if bot is not None:
		log("Re-creating bot object..")

	success = False
	dropoff = 0.5

	while not success:
		try:
			bot = ChatBot(bot_name, password, channel_name, debug=False, capabilities=["tags", "commands"])
			commands_file.bot = bot
			success = True
		except Exception as ex:
			log(f"Bot raised an exception while starting: {str(ex)}. Waiting {dropoff}s.")
			sleep(dropoff)
			dropoff *= 2

def ban_lurker_bots():
	global bots
	viewers_url = "https://tmi.twitch.tv/group/user/kaywee/chatters"
	bots_url = "https://api.twitchinsights.net/v1/bots/all"
	allowed_bots = bots
	check_period = 60*30 # 30 minutes

	last_lurker_check = get_data("last_lurker_check", 0)

	time_since = time() - last_lurker_check
	if time_since <= check_period:
		wait_time = check_period - time_since
		sleep(wait_time)	

	recently_banned = get_data("recently_banned", [])

	while True:
		channel_live.wait() # if channel goes offline, wait for it to come back online before continuing. We'll still check a few times below after the channel goes offline
		try:
			known_bots = requests.get(bots_url).json()["bots"]

			# the above returns a list of lists like [["botname", number_of_channels, "something else idk"], [..]]
			# so for each bot in the list, bot[0] is the name; bot[1] is the number of channels it's in.
			# Idk that's just how it comes through ok
			# so this makes it into a dict of {name: numchannels}:
			known_bots = dict([(bot[0], bot[1]) for bot in known_bots]) 
			assert len(known_bots) > 0 # bit of a sanity check
		except Exception as ex:
			log("Exception while fetching lurker bots list: " + str(ex) + " - using cached bots list")
			try:
				with open("known_bots.txt", "r", encoding="utf-8") as f:
					known_bots = dict(eval(f.read()))

				assert len(known_bots) > 0 # bit of a sanity check
			except Exception as ex:
				log("Failed to read cached bots list. Sleeping - trying again later.")
				sleep(check_period)
				continue # restarts at the while True above

		else:
			with open("known_bots.txt", "w", encoding="utf-8") as f:
				f.write(str(known_bots))

		for _ in range(24): # only update the known_bots list every 24 checks (12 hours @ 30m/check). Reduces api calls and there's a lot of data (4MB?!)
			try:
				viewers = requests.get(viewers_url).json()["chatters"]["viewers"] # doesn't list broadcaster, vips, mods, staff, admins, or global mods. Which is good here.
			except Exception as ex:
				log("Exception while checking for lurker bots: " + str(ex))
			else:
				for viewer in viewers:
					# allow anyone who's ever chatted (usernames list)
					# exclude allowed bots
					# check they're in the known bot list
					# check they're lurking in at least 100 channels
					# check we've not already banned them
					if (viewer not in usernames) and (viewer not in allowed_bots) and (viewer in known_bots) and (known_bots[viewer] > 100) and (viewer not in recently_banned):
						send_message(f"/ban {viewer}")
						send_discord_message(f"The following uninvited lurker bot has been banned on Twitch: {viewer}")
						log(f"Banned known bot {viewer} for uninvited lurking.")
						recently_banned.append(viewer)
						if len(recently_banned) > 10:
							recently_banned = recently_banned[-10:]
						set_data("recently_banned", recently_banned)
						sleep(3) # just helps space the messages out a bit

				set_data("last_lurker_check", int(time()))
			sleep(check_period)

def send_discord_message(message):
	# don't wanna block up the main thread while the discord bot starts up and sends the message
	p = Thread(target=_send_discord_message, args=(message,)).start()

def _send_discord_message(message):
	# this takes a few seconds and probably shouldn't be used too much LOL
	try:
		# fuck discord.py and it's async bs for making me do this
		subprocess.run("python discord.py " + message, capture_output=True) # capture_output=True means the output doesn't go to console.. Otherwise when it exit()s it prints the exception stack lol
	except Exception as ex:
		log("Exception sending discord message: " + str(ex))
		return

def get_twitch_emotes():
	global twitch_emotes
	result = requests.get("https://api.streamelements.com/kappa/v2/chatstats/kaywee/stats").json()
	twitchEmotes = result.get("twitchEmotes", [])
	twitch_emotes = [item["emote"] for item in twitchEmotes]

def get_emote(emote):
	global subscribers
	global twitch_emotes

	if emote[:7] == "kaywee1" and "robokaywee" not in subscribers: # sub emotes can only be used while bot is subbed
		return ""
	else:
		if emote in twitch_emotes: # emote must be valid
			return emote
		else:
			return ""

def get_oauth_token(force_new_token=False):
	kaywee_oauth_expiry = get_data("kaywee_oauth_expiry")

	if force_new_token or kaywee_oauth_expiry < time():
		try:
			kaywee_oauth_refresh_token = get_data("kaywee_oauth_refresh_token")
			url = "https://id.twitch.tv/oauth2/token"
			refresh_params = {
						"grant_type"    : "refresh_token",
						"refresh_token" : kaywee_oauth_refresh_token,
						"client_id"     : robokaywee_client_id,
						"client_secret" : robokaywee_secret
						}
			result = requests.post(url, params=refresh_params).json()

			kaywee_oauth_token = result["access_token"]
			new_expiry = result["expires_in"]
			new_refresh_token = result["refresh_token"]

			set_data("kaywee_oauth_expiry", int(time() + new_expiry))
			set_data("kaywee_oauth_refresh_token", new_refresh_token)
			set_data("kaywee_oauth_token", kaywee_oauth_token)

			return kaywee_oauth_token
		except KeyError as ex:
			log(f"No Token received when fetching new oauth token from twitch - {str(ex)}")
			raise # re-raise the same exception so the calling function doesn't continue
	else:
		kaywee_oauth_token = get_data("kaywee_oauth_token")

		try:
			result = requests.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": "OAuth " + kaywee_oauth_token}).json()
			new_expiry = result["expires_in"] # number of seconds from now. (not a timestamp!)
			assert new_expiry > 0

			set_data("kaywee_oauth_expiry", int(time() + new_expiry))
			return kaywee_oauth_token

		except Exception as ex:
			log(f"Exception when validating oauth token - {str(ex)} - trying again with force_new_token..")
			return get_oauth_token(force_new_token=True)

def dont_stop_comin():
	while True:
		channel_live.wait() # if channel goes offline, wait for it to come back online
		sleep(random.randint(45*60, 100*60)) # random wait between 45 and 100 mins
		if channel_live.is_set(): # channel is still online after sleeping
			send_message("and they don't stop comin'")
			log("and they don't stop comin'")

def respond_message(message_dict):
	# For random non-command responses/rules
	# This is run on a second thread

	global bUrself_sent # this is needed
	global ali_sent     # this too
	global twitch_emotes

	user       = message_dict["display-name"].lower()
	message    = message_dict["message"]
	permission = message_dict["user_permission"]

	message_lower = message.lower()
	msg_lower_no_punc = "".join(c for c in message_lower if c in ascii_lowercase+" ")
	msg_words = [word for word in message_lower.split(" ") if word not in twitch_emotes] # remove emotes

	if "@robokaywee" in message_lower and user not in bots and permission < permissions.Mod:
		send_message(f"@{user} I'm a bot, so I can't reply. Try talking to one of the helpful human mods instead.")
		log(f"Sent \"I'm a bot\" to {user}")

	elif commands_file.nochat_on and user not in bots and "kaywee" in message_lower:
		message_lower = " ".join(msg_words).replace("robokaywee", "") # stitch message back together and remove robokaywee

		if "kaywee" in message_lower:
			send_message(f"@{user} {commands_dict['nochat']['response']}")
			log(f"Sent nochat to {user} in response to @kaywee during nochat mode.")

	elif permission < permissions.Subscriber:
		msg_without_spaces = message_lower.replace(" ", "")
		if any(x in msg_without_spaces for x in ["bigfollows.com", "bigfollows*com", "bigfollowsdotcom", "wannabecomefamous?", "buyfollowersandviewers", "clck.ru", "mountviewers", "t.ly/cgtm"]):
			send_message(f"/ban {user}")
			log(f"Banned {user} for linking to spam")
			send_discord_message(f"The following bigfollows spammer has been banned on Twitch: {user}")

	# EASTER EGGS:
	
	if message[0] == "^":
		send_message("^") #, suppress_colour=True)
		log(f"Sent ^ to {user}")
	elif ayy_re.fullmatch(message_lower):
		send_message("lmao")
		log(f"Sent lmao to {user}")
	elif message_lower in ["hewwo", "hewwo?", "hewwo??"]:
		send_message(f"HEWWO! UwU {get_emote('kaywee1AYAYA')}")
		log(f"Sent hewwo to {user}")
	elif message_lower == "hello there":
		send_message("General Kenobi")
		log(f"Sent Kenobi to {user}")
	#elif "romper" in message_lower:
	#	send_message("!romper")
	#	log(f"Sent romper to {user}")
	elif user == "theonefoster" and message_lower == "*sd":
		global shutdown_on_offline
		shutdown_on_offline = True
		log("Will now shutdown when Kaywee goes offline.")
	elif user == "nightroad2593" and message_lower[:6] == "in ow2":
		log(f"Saved new ow2 prediction: {message_lower}")
		with open("ow2.txt", "a") as f:
			f.write(message + "\n")
	#elif user in ["gothmom_", "ncal_babygirl24"] and "lucio" in message_lower:
	#	send_message("IS UR MAN HERE??")
	#	log(f"Sent \"Is your man here?\" to {user}")
	elif msg_lower_no_punc == "alexa play despacito":
		send_message("Now playing Despacito by Luis Fonsi.")
		log(f"Now playing Despacito for {user}")
	elif msg_lower_no_punc == "alexa stop":
		send_message("Now stopping.")
		log(f"Stopping Alexa for {user}")
	elif len(msg_words) == 2 and msg_words[0].lower() in ["im", "i'm", "i’m"] and all(x in printable[:36] for x in msg_words[1]): #printable[:36] is 0-9 and lowercase a-z
		send_message(f"Hi {msg_words[1]}, I'm dad!")
		log(f"Sent Dad to {user}")
	elif not bUrself_sent and user == "billneethesciencebee":
		send_message("bUrself")
		bUrself_sent = True
		set_data("bUrself_sent", True)
		log(f"Sent bUrself to {user}")
	elif not ali_sent and user == "aliadam80":
		send_message(commands_dict["ali"]["response"])
		ali_sent = True
		set_data("ali_sent", True)
		log(f"Sent Ali pasta to {user}")
	elif re.fullmatch(patrick_re, message_lower):
		send_message("No, this is Patrick.")
		log(f"Sent patrick to {user}")
	elif msg_lower_no_punc in ["modcheck", "mod check"]:
		send_message(":eyes:")
		log(f"Sent ModCheck to {user}")
	elif message == "Jebaited":
		send_message("Jebaited https://www.youtube.com/watch?v=d1YBv2mWll0 Jebaited")
		log(f"Sent Jebaited song to {user}")
	elif re.fullmatch(sheesh_re, message_lower):
		send_message(message.upper())
	elif re.fullmatch(aaa_re, message_lower):
		send_message(message + "!!")
		log(f"Sent aaaaaa to {user}")
	elif any(len(word) > 3 and word.startswith("xqc") for word in msg_words):
		send_message("KEKW Using KEKW xQc KEKW emotes KEKW unironically KEKW")
		log(f"Sent KEKW to {user}'s xQc emote")
	elif "onlyfans" in message_lower:
		send_message("Onlyfans? Kaywee's is at http://kaywee.live/onlyfans")
		log(f"Sent Kaywee's onlyfans to {user}")

class permissions(IntEnum):
    Disabled    = 20
    Owner       = 12
    Broadcaster = 10
    Mod	        = 8
    VIP	        = 6
    Subscriber  = 4
    Follower    = 2
    Pleb        = 0

update_command_data = False # does command data on disk/wiki need to be updated?

#check for new commands and add to database:
for command_name in [obj for obj in dir(commands_file) if not(obj[0] == "_" or obj[-1] == "_")]:
	try:
		if getattr(commands_file, command_name).is_command is True: # "is" requires it to be explicitly True, rather than "truthy" e.g. non-empty lists/strings, ints>0 etc
			if command_name not in commands_dict:
				commands_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 0, 'coded': True, 'uses': 0, "description": getattr(commands_file, command_name).description}
				update_command_data = True
			else:
				command_description = getattr(commands_file, command_name).description
				if "description" not in commands_dict[command_name] or commands_dict[command_name]["description"] != command_description:
					commands_dict[command_name]["description"] = command_description # add/update description
					update_command_data = True
	except AttributeError:
		pass

if update_command_data:
	write_command_data(force_update_reddit=False)

del update_command_data

if __name__ == "__main__":
	log("Starting bot..")

	success = False
	dropoff = 0.5

	create_bot()

	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + get_data("app_access_token")}

	Thread(target=get_twitch_emotes,       name="Get Twitch emotes").start()
	Thread(target=channel_events,          name="Channel Events").start()
	Thread(target=update_app_access_token, name="Access Token Updater").start()
	Thread(target=update_subs,             name="Subscriber Updater").start()	
	Thread(target=update_followers,        name="Followers Updater").start()
	Thread(target=set_random_colour,       name="Colour Updater").start()
	Thread(target=channel_live_messages,   name="Channel Live Messages").start()
	Thread(target=automatic_backup,        name="Automatic Backup").start()
	Thread(target=play_patiently,          name="Play Patiently").start()
	Thread(target=ban_lurker_bots,         name="Ban Lurker Bots").start()
	#Thread(target=dont_stop_comin,         name="Don't Stop Coming").start()
	#Thread(target=ow2_msgs,                name="OW2 messages").start()
	
	user_cooldowns  = {}
	modwall_mods    = set()
	modwall         = get_data("modwall", 0)
	current_modwall = None
	vip_wall        = 0
	vipwall_vips    = set()
	last_message    = {}
	dropoff         = 1
	bUrself_sent    = get_data("bUrself_sent", False)
	ali_sent        = get_data("ali_sent", False)
	user_messages   = get_data("user_messages", {})
	
	# let commands file access key objects
	# these can be read and written to from both here and commands_file
	commands_file.bot                = bot
	commands_file.log                = log
	commands_file.get_data           = get_data
	commands_file.set_data           = set_data
	commands_file.nochat_on          = False
	commands_file.get_emote          = get_emote
	commands_file.usernames          = usernames
	commands_file.subscribers        = subscribers
	commands_file.permissions        = permissions
	commands_file.send_message       = send_message
	commands_file.command_dict       = commands_dict
	commands_file.last_message       = last_message
	commands_file.user_messages      = user_messages
	commands_file.get_oauth_token    = get_oauth_token
	commands_file.write_command_data = write_command_data

	print(f"Setup complete. Listening in {channel_name}'s chat.")

	while True:
		try:
			#messages = [{"message_type":"privmsg", "display-name":"theonefoster", "message":"!translate en de this is a test!", "badges":["moderator"], "id":"testmessageid"}] # for testing, uncomment and change message
			messages = bot.get_messages()
			for message_dict in messages:
				if message_dict["message_type"] != "privmsg" and message_dict["message_type"] != "userstate":
					with open("weird_messages.txt", "a", encoding="utf-8") as f:
						f.write(str(message_dict) + "\n\n")
				if message_dict["message_type"] == "privmsg": # chat message
					user	= message_dict["display-name"].lower()
					message = message_dict["message"]
					message_lower = message.lower()

					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"{user}: {message}\n")

					if user not in usernames:
						Thread(target=add_new_username,args=(user,)).start() # probably saves like.. idk 50ms? over just calling it.. trims reaction time though
					elif hello_re.fullmatch(message_lower): # Hello isn't sent to new users - they get the greeting instead, not as well.
						if user == "littlehummingbird":
							send_message("HELLO MADDIE THIS IS TOTALLY NOT A SASSY MESSAGE BUT HI") # little easter egg for maddie :)
							log("Said Hello to Maddie, but in a totally not-sassy way")
						else:
							message = "!hello" # react as if they used the command

					last_message[user] = {"message":message, "ID": message_dict["id"]} # maybe the ID too? From ["target-msg-id"]. Or just the whole dict.
					user_permission = permissions.Pleb # unless assigned otherwise below:
						
					if user == "theonefoster":
						user_permission = permissions.Owner
					elif "badges" in message_dict: # twitch recommends using badges instead of the deprecated user-type tag
						if "broadcaster" in message_dict["badges"]:
							user_permission = permissions.Broadcaster
						elif "moderator" in message_dict["badges"]:
							user_permission = permissions.Mod
						elif "vip/1" in message_dict["badges"]:
							user_permission = permissions.VIP
						elif "subscriber" in message_dict["badges"]:
							user_permission = permissions.Subscriber
						elif user in followers:
							user_permission = permissions.Follower

					message_dict["user_permission"] = user_permission

					if message_lower[:6] == "alexa ":
						message_letters = "".join(char for char in message_lower if char in ascii_lowercase+" ")
						if message_letters not in ["alexa play despacito", "alexa stop"]:
							message = "!" + message[6:]
							message_dict["message"] = message

					if message[0] == "!":
						command = message[1:].split(" ")[0].lower()
						if command in ["win", "loss", "draw"]:
							command = "toxicpoll" # start a toxicpoll when the SE result commands are seen
						if command in commands_dict:
							command_obj = commands_dict[command]
							                                                     # cooldowns now only apply to non-mods. bc fuck those guys
							if user_permission >= command_obj["permission"] and (user_permission >= permissions.Mod or check_cooldown(command, user)):
								if command_obj["coded"]:
									if command in dir(commands_file):
										func = getattr(commands_file, command)
										if func.is_command is True: # "is" stops "truthy" values from proceeding. It needs to be explicitly True to pass
											if func(message_dict) != False: # commands can return True/None on success (None != False)
												if "uses" in command_obj:
													command_obj["uses"] += 1
												else:
													command_obj["uses"] = 1

												command_obj["last_used"] = round(time(), 1) # doesn't need more than 0.1s precision and decimal places take up bytes!
												write_command_data(force_update_reddit=False)
										else:
											log(f"**WARNING**: tried to call non-command function: {command}")
									else:
										log(f"**WARNING**: Stored coded command with no function: {command}")
								else:
									if "response" in command_obj and command_obj["response"]:
										words = message.split(" ")
										response = command_obj["response"]

										if len(words) == 2 and words[1][0]=="@":
											msg_to_send = words[1] + " " + response
										else:
											msg_to_send = response

										send_message(msg_to_send)
										log(f"Sent {command} in response to {user}.")

										if "uses" in command_obj:
											command_obj["uses"] += 1
										else:
											command_obj["uses"] = 1

										command_obj["last_used"] = round(time(), 1)
										write_command_data(force_update_reddit=False)
									else:
										log(f"**WARNING**: Stored text command with no response: {command}")
					else:
						Thread(target=respond_message, args=(message_dict,)).start()

					if user_permission >= permissions.Mod:
						modwall_mods.add(user)

						# don't send modwall unless there are at least 3 mods in the wall
						if  (    modwall <  14                             # few messages, OR
							 or (modwall >= 14 and len(modwall_mods) >= 3) # lots of messages and at least 3 mods
							): # sadface 

							modwall += 1
							if modwall in modwalls:
								modwall_data = modwalls[modwall]
								current_modwall = modwall_data["name"]
								excitement = "!"*modwall_data["excitement"]

								send_message(f"#{current_modwall}{'!'*modwall_data['excitement']} {modwall_data['emotes']}")
								log(f"{current_modwall}{'!'*modwall_data['excitement']}")
							if modwall >= 5:
								set_data("modwall", modwall)
					else:
						if modwall >= modwall_break_level:
							modwall_data = get_modwall(modwall)
							current_modwall = modwall_data["name"]
							break_emotes = modwall_data["break_emotes"]
							excitement = "!"*modwall_data["excitement"]
							send_message(f"{current_modwall} has been broken by {user}{excitement} {break_emotes}")

						if modwall >= 5:
							set_data("modwall", 0)

						modwall = 0
						modwall_mods = set()
						current_modwall = None

					# future me: don't indent this (otherwise mods can't interrupt vipwalls)
					if user_permission == permissions.VIP:
						vip_wall += 1

						if vip_wall == 15:
							send_message(f"#VIPwall! {get_emote('kaywee1AYAYA')}")
							log("VIPwall!")
						elif vip_wall == 30:
							send_message("#SUPER VIPwall! PogChamp")
							log("SUPER VIPwall!")
						elif vip_wall == 60:
							send_message("#MEGA VIPwall! PogChamp Kreygasm CurseLit")
							log("MEGA VIPwall!")
						elif vip_wall == 120:
							send_message(f"#U L T R A VIPwall! PogChamp Kreygasm CurseLit FootGoal {get_emote('kaywee1Wut')}")
							log("U L T R A VIPwall!")
					else:
						vip_wall = 0
						vipwall_vips = set()

					if user in user_messages:
						user_message_info = user_messages[user]
						from_user    = user_message_info["from_user"]
						user_message = user_message_info["user_message"]

						del user_messages[user]
						
						send_message(f"@{user}, you have a message from {from_user}: {user_message}")
						log(f"Sent a user message from {from_user} to {user}. It says: {user_message}")
						set_data("user_messages", user_messages)

				elif message_dict["message_type"] == "notice":
					if "msg_id" in message_dict: # yes.. it's msg_id here but msg-id everywhere else. Why? Who knows. Why be consistent?
						id = message_dict["msg_id"]
						if "message" in message_dict:
							if id != "color_changed": # gets spammy with daily colour changes and rainbows etc
								if id == "host_on":
									channel_went_offline() # trigger end of stream events
									
								message = message_dict["message"]
								log(f"NOTICE: {id}: {message}")
								with open("chatlog.txt", "a", encoding="utf-8") as f:
									f.write(f"NOTICE: ({id}): {message}\n")
						else:
							log(f"NOTICE with msg_id but no message: {str(message_dict)}") # shouldn't happen
					else:
						log(f"NOTICE with no msg_id: {str(message_dict)}") # shouldn't happen

				elif message_dict["message_type"] == "usernotice":
					if "msg-id" in message_dict:
						if message_dict["msg-id"] == "subgift": # GIFTED SUBSCRIPTION
							gifter = message_dict["display-name"].lower()
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {gifter} has gifted a subscription to {recipient}\n")
							subscribers[recipient] = {"gifter_name":gifter, "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{gifter} has gifted a sub to {recipient}!")

							if recipient == "robokaywee":
								sleep(1)
								send_message(f"OMG {gifter}!! Thank you so much for my gifted sub, you're the best!! <3 <3 kaywee1AYAYA") # don't get_emote as we know the bot is subbed
							elif commands_file.nochat_on:
								send_message(f"@{gifter} thank you so much for gifting a subscription to {recipient}! Kaywee isn't looking at chat right now (!nochat) but she should see your gift after her current game.")
								log(f"Sent nochat to {gifter} for gifting a sub")

						elif message_dict["msg-id"] == "sub": # USER SUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has subscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has subscribed!")

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for subscribing! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for subscribing")

						elif message_dict["msg-id"] == "resub": # USER RESUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has resubscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has resubscribed!")

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for resubscribing! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for resubscribing")

						elif message_dict["msg-id"] == "anonsubgift": # ANONYMOUS GIFTED SUBSCRIPTION
							# this has never come through. I just get msg-id="sub" with gifter of AnAnonymousGifter. So why tf does this message type exist?
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: AnAnonymousGifter has gifted a subscription to {recipient}!\n")
							subscribers[recipient] = {"gifter_name":"AnAnonymousGifter", "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "raid": # incoming raid
							raider = message_dict["msg-param-displayName"]
							viewer_count = message_dict["msg-param-viewerCount"]
							if int(viewer_count) >= 2:
								with open("chatlog.txt", "a", encoding="utf-8") as f:
									f.write(f"USERNOTICE: {raider} is raiding with {viewer_count} viewers!\n")
								send_message(f"Wow! {raider} is raiding us with {viewer_count} new friends! Thank you! {get_emote('kaywee1AYAYA')}")
								log(f"{raider} is raiding with {viewer_count} viewers.")
								raid_data = {"raider": raider, "viewers": viewer_count, "time": int(time())}
								raid_data = str(raid_data).replace(", ", ",") # set_data() replaces ", " with ",\n", but I don't want that to apply to this dict, so removing the space stops it being picked up by that .replace()
								set_data("last_raid", raid_data)

								if commands_file.nochat_on:
									Thread(target=nochat_raid, params=(raider)).start()
									# sends a message in chat after a short delay

								if raider.lower() == "toniki":
									def how_to_translate_thread():
										sleep(20)
										send_message(commands_dict["howtotranslate"]["response"])

									Thread(target=how_to_translate_thread).start()

								Thread(target=promote_socials, name="Socials (Raid)", args=(300,)).start() #after 300 seconds (5 mins), promote socials

						elif message_dict["msg-id"] == "submysterygift":
							gifter = message_dict["login"] # comes as lowercase
							gifts = message_dict["msg-param-mass-gift-count"]

							if gifts != "1":
								log(f"{gifter} has gifted {gifts} subscriptions to the community!")
							else:
								log(f"{gifter} has gifted a subscription to the community!")

						elif message_dict["msg-id"] == "giftpaidupgrade":
							subscriber = message_dict["msg-param-sender-login"] 

							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {subscriber} has continued their gifted sub.\n")
							log(f"{subscriber} has continued their gifted sub.")

							subscribers[subscriber] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()

							if commands_file.nochat_on:
								send_message(f"@{user} thank you for continuing your gifted sub! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for subscribing")
								
						elif message_dict["msg-id"] == "rewardgift":
							pass # for when gifted subs produce extra rewards (emotes) for other chat members

						elif message_dict["msg-id"] == "communitypayforward":
							# e.g. <user> is paying forward their gifted sub to the community!
							gifter = message_dict["msg-param-prior-gifter-display-name"]
							recipient = message_dict["msg-param-recipient-display-name"]

						elif message_dict["msg-id"] == "standardpayforward":
							# e.g. <user> is paying forward their gifted sub to <recipient>!
							gifter = message_dict["msg-param-prior-gifter-display-name"]
							recipient = message_dict["msg-param-recipient-display-name"]

						elif message_dict["msg-id"] == "bitsbadgetier":
							badge_user      = message_dict["display-name"]
							badge_threshold = message_dict["msg-param-threshold"]
							send_message(f"@{badge_user} just earned a new bits badge tier for sending over {badge_threshold} total bits to Kaywee! Thank you!")
							log(f"Congratulated {badge_user} who now has a {badge_threshold}-bits badge.")

						elif message_dict["msg-id"] == "primepaidupgrade":
							upgrade_user = message_dict["display-name"]
							# user is upgrading from a prime sub to a regular sub

						elif message_dict["msg-id"] == "unraid":
							# e.g. "The raid has been cancelled."
							pass
						elif message_dict["msg-id"] == "ritual":
							# 04/11/21 - this didn't come through in chat for a new user who redeemed Highlight My Message. Old set method detected the new user but new ritual method didn't.

							# update: doesn't work. ritual msg doesn't come through at all.
							if message_dict["msg-param-ritual-name"] == "new_chatter":
								new_chatter = message_dict["display-name"]
								log(f"{new_chatter} is a new chatter!")
							else:
								with open("verbose log.txt", "a", encoding="utf-8") as f:
									f.write("unknown ritual - " + str(message_dict) + "\n\n")
						else:
							with open("verbose log.txt", "a", encoding="utf-8") as f:
								f.write("(unknown msg-id?) - " + str(message_dict) + "\n\n")
						 # other sub msg-ids: sub, resub, subgift, anonsubgift, submysterygift, giftpaidupgrade, rewardgift, anongiftpaidupgrade
					else:
						with open("verbose log.txt", "a", encoding="utf-8") as f:
							f.write("(no msg-id?) - " + str(message_dict) + "\n\n")
				elif message_dict["message_type"] == "hosttarget":
					# OUTGOING HOST
					host_name = message_dict["host_target"] # the user we're now hosting
					viewers = message_dict["viewers"] # num viewers we've sent to them
					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"HOSTTARGET: now hosting {host_name} with {viewers} viewers.\n")
					log(f"Now hosting {host_name} with {viewers} viewers.")
					if int(viewers) > 1:
						send_message(f"Now hosting {host_name} with {viewers} viewers.")

				elif message_dict["message_type"] == "userstate":
					# Mostly just for colour changes which I don't care about
					# update: It's not even for colour changes.. one seems to come through every time I use /me.. what does this mean?? docs don't help :/
					pass

					"""
					user       = message_dict.get("display-name", None) # username, case-sensitive
					colour     = message_dict.get("color"       , None) # Hexadecimal RGB color code
					badge_info = message_dict.get("badge-info"  , None) # Metadata related to chat badges. Details subscription length in months
					badges     = message_dict.get("badges"      , None) # comma-separated list of chat badges
					emote_sets = message_dict.get("emote-sets"  , None) # list of ints
					mod        = message_dict.get("mod"         , None) # 1 iff user has mod badge, else 0
					"""

				elif message_dict["message_type"] == "roomstate":
					# If the chat mode changes, e.g. entering or leaving subs-only or emote-only mode
					if "emote-only" in message_dict:
						enabled_str = "enabled" if int(message_dict.get("emote-only", 0)) else "disabled"
						send_message(f"Emote-only mode is now {enabled_str}")

					elif "followers-only" in message_dict:
						duration = message_dict["followers-only"]
						if duration == "-1":
							send_message(f"Followers-only mode is now disabled")
						else:
							send_message(f"Followers-only mode is now set to {duration} minutes.")

					elif "r9k" in message_dict:
						enabled_str = "enabled" if int(message_dict.get("r9k", 0)) else "disabled"
						send_message(f"r9k mode is now {enabled_str}")

					elif "slow" in message_dict:
						duration = int(message_dict["slow"])
						send_message(f"Slow mode is now set to {duration} seconds.")

					elif "subs-only" in message_dict:
						enabled_str = "enabled" if int(message_dict.get("subs-only", 0)) else "disabled"
						send_message(f"Subs-only mode is now {enabled_str}")

						with open("verbose log.txt", "a", encoding="utf-8") as f:
							f.write("Robokaywee - unknown roomstate: " + str(message_dict) + "\n\n")

				elif message_dict["message_type"] == "clearmsg":
					# single message was deleted
					# e.g {'message_type': 'clearmsg', 'login': 'nacho_888', 'room-id': '', 'target-msg-id': '4e2100ba-f5fe-4338-85a1-cccc191375c7', 'tmi-sent-ts': '1613065616305'}
					target = message_dict["login"] # the user whose message was deleted ?
					print(message_dict)

				elif message_dict["message_type"] == "clearchat":
					# cleared all messages from user
					user_id = message_dict.get("target-user-id", None) # this is the User ID, not the username. It's a str-formatted number.
					print(message_dict)
					# username = get_name_from_user_ID(user_id)
				else:
					current_time = localtime()
					# year   = str(current_time.tm_year)
					month  = str(current_time.tm_mon ).zfill(2)
					day    = str(current_time.tm_mday).zfill(2)
					hour   = str(current_time.tm_hour).zfill(2)
					minute = str(current_time.tm_min ).zfill(2)
					second = str(current_time.tm_sec ).zfill(2)
					
					log_time = f"{day}/{month} {hour}:{minute}:{second}"
					with open("verbose log.txt", "a", encoding="utf-8") as f:
						f.write(log_time + " - Robokaywee - unknown message type: " + str(message_dict) + "\n\n")
			dropoff = 1
		except Exception as ex:
			if any(x in str(ex) for x in ["An existing connection was forcibly closed", "An established connection was aborted"]):
				log(f"Connection was closed - will try again in {int(dropoff)}s..")
				try:
					create_bot() # re-create bot object (to reconnect to twitch)
				except Exception as ex:
					pass # this will cause the loop to continue, and if the bot object fails to recreate the dropoff will increase in the next catch
			else:
				log("Exception in main loop: " + str(ex)) # generic catch-all (literally) to make sure bot doesn't crash

			dropoff = min(dropoff * 1.5, 600) # exponential dropoff, decay factor 1.5, but don't wait longer than 10 mins
			sleep(dropoff)