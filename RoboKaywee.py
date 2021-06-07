#import sqlite3 # one day maybe I'll use an actual database LOL
import os
import re
import praw # takes 0.33s to import!
import random
import requests
import subprocess

from os          import getcwd
from time        import time, sleep, localtime
from enum        import IntEnum
from math        import ceil
from james       import timeuntil #, is_haiku # takes 0.4s to import!
from string      import ascii_lowercase
from shutil      import copy2 as copy_with_metadata
from chatbot     import ChatBot # see https://github.com/theonefoster/pyTwitchChatBot
from datetime    import date, datetime
from threading   import Thread, Lock, Event
from contextlib  import suppress
from credentials import bot_name, password, channel_name, kaywee_channel_id, robokaywee_client_id, tof_channel_id

import commands as commands_file # takes 0.3s to import!
from API_functions import get_app_access_token, get_name_from_user_ID, get_followers

"""
TODO:
should be able to give any command multiple names via aliases
when host_on notice is received, channel_live should be set to false
rework how live detection works
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
	year   = str(current_time.tm_year)
	month  = str(current_time.tm_mon ).zfill(2)
	day    = str(current_time.tm_mday).zfill(2)
	hour   = str(current_time.tm_hour).zfill(2)
	minute = str(current_time.tm_min ).zfill(2)
	second = str(current_time.tm_sec ).zfill(2)
	
	log_time = f"{day}/{month} {hour}:{minute}:{second}"

	print(f"{hour}:{minute} - {s}")
	with open("log.txt", "a", encoding="utf-8") as f:
		f.write(log_time + " - " + s + "\n")

command_lock   = Lock()
config_lock    = Lock()
subs_lock      = Lock()
usernames_lock = Lock()
wiki_lock      = Lock()

channel_live        = Event()
channel_offline     = Event()
live_status_checked = Event()
live_status_checked.clear()

bots = {"robokaywee", "streamelements", "nightbot"}

bot = None
shutdown_on_offline = False # can be set to true to shutdown pc when streamer goes offline

# some regexes for detecting certain message patterns
ayy_re     = re.compile("a+y+") # one or more "a" followed by one or more "y", e.g. aayyyyy
hello_re   = re.compile("h+i+|h+e+y+|h+e+l+o+|h+o+l+a+|h+i+y+a+") # various ways of saying hello
patrick_re = re.compile("is this [^ ]*\?*$") # "is this " followed by a word, followed by zero or more question marks. e.g. "is this kaywee??"

# when only mods send messages into chat for at least X messages, the bot will announce the modwall.
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
	250: {"name": "U L T R A M O D W A L L", "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 3, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands"},
	500: {"name": "G I G A M O D W A L L",   "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 3, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	# I guarantee none of these will ever be reached naturally, but..
	1000:{"name": "PETAMODWALL",             "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 4, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	2000:{"name": "EXAMODWALL",              "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 5, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	3000:{"name": "ZETTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 6, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	4000:{"name": "YOTTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut", "excitement": 7, "break_emotes": ":( FeelsBadMan NotLikeThis PepeHands Sadge"},
	# also I know that the SI prefixes don't match the numbers but whatever, I needed increasing prefixes
}

get_modwall = lambda x: modwalls[sorted(list(key for key in modwalls.keys() if key <= x))[-1]] # you can do it moldar
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

def channel_events():
	""" 
	Checks the channel every period. If channel goes live or goes offline, global Thread events are triggered.
	Dont you dare judge my code quality in this function Flasgod. I know it's a mess but we do what we gotta do to survive.
	"""

	global channel_live
	global channel_offline
	global live_status_checked
	global shutdown_on_offline
	global bUrself_sent
	global ali_sent

	def check_live_status_first():
		nonlocal online_time 
		try:
			# if this call succeeds, streamer is Live. Exceptions imply streamer is offline (as no stream title exists)
			title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]

		# streamer is offline:
		except (IndexError, KeyError): 
			if online_time is not None: # streamer went offline while bot was offline
				uptime = int(time() - online_time)

				hours = int((uptime % 86400) // 3600)
				mins  = int((uptime % 3600) // 60)
				# seconds = int (uptime % 60) # uptime isn't precise enough to justify sending the seconds

				log(f"{channel_name} went offline. Uptime was {hours} hours and {mins} mins.")

				online_time = None
				set_data("online_time", None)

			channel_offline.set()

		# streamer is online:
		else:
			if online_time is None: # streamer came online while bot was offline
				log(f"{channel_name} is online.")
				online_time = time() # set first time seen online
				set_data("online_time", online_time)
				bUrself_sent = False
				set_data("bUrself_sent", False)
				ali_sent = False
				set_data("ali_sent", False)
				set_data("wordoftheday_sent", False)
				set_data("unpink_sent", False)
				set_data("worldday_sent", False)
				
			channel_live.set()

			add_seen_title(title) # save unique stream title

	def check_live_status_subsequent():
		nonlocal online_time
		global shutdown_on_offline
		try:
			# if this call succeeds, streamer is Live. Exceptions imply streamer is offline (as no stream title exists)
			title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]

		# streamer is offline:
		except (IndexError, KeyError): 
			if channel_live.is_set(): # streamer went offline in last period
				uptime = int(time() - online_time)

				hours = int((uptime % 86400) // 3600)
				mins  = int((uptime % 3600) // 60)
				# seconds = int (uptime % 60)

				uptime_string = f"{channel_name} went offline. Uptime was approximately {hours} hours and {mins} mins."

				log(uptime_string)
				send_message(uptime_string)

				online_time = None
				set_data("online_time", None)

				channel_live.clear()
				channel_offline.set()

				if shutdown_on_offline:
					log("Shutting down the PC..")
					sleep(1)
					subprocess.run("Shutdown /s /f")

		# streamer is online:
		else:
			if not channel_live.is_set(): # streamer CAME online in last period
				log(f"{channel_name} came online.")
				online_time = time() # set first time seen online
				set_data("online_time", online_time)
				
				channel_offline.clear()
				channel_live.set()

				bUrself_sent = False
				set_data("bUrself_sent", False)
				ali_sent = False
				set_data("ali_sent", False)
				set_data("wordoftheday_sent", False)
				set_data("unpink_sent", False)
				set_data("worldday_sent", False)

			add_seen_title(title) # save unique stream title
	try:
		online_time = get_data("online_time")
	except Exception as ex:
		log("Exception reading online_time: " + str(ex))
		online_time = None
	
	period = 120

	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	global authorisation_header

	check_live_status_first()
	live_status_checked.set() # signal to other threads that first run is complete

	while True:
		try:
			check_live_status_subsequent()
		except Exception as ex:
			log("Exception which checking Live Status: " + str(ex))

		sleep(period)

def play_patiently():
	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	global authorisation_header

	reminder_period = 60*60

	last_patient_reminder = get_data("last_patient_reminder", 0)

	time_since = time() - last_patient_reminder
	if time_since <= reminder_period:
		wait_time = reminder_period - time_since
	else:
		wait_time = 0

	sleep(wait_time)

	while True:
		try:
			title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"] # makes sure streamer is live
			send_message("@Kaywee - Reminder: play patiently!")
			log("Sent patient reminder.")
			set_data("last_patient_reminder", int(time()))
		except:
			pass

		sleep(reminder_period) # wait an hour before retrying

last_wiki_update = 0
def update_commands_wiki(force_update_reddit=False):
	global last_wiki_update
	global permissions

	if force_update_reddit or last_wiki_update < time() - 60*30: # don't update more often than 30 mins unless forced
		#permissions_dict = {0:"Pleb", 2:"Follower", 4:"Subscriber", 6:"VIP", 8:"Mod", 9:"Owner", 10:"Broadcaster", 20:"Disabled"}
		permissions_dict = {p.value : p.name for p in permissions}

		r = praw.Reddit("RoboKaywee")
		subreddit = r.subreddit("RoboKaywee")

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

			subreddit.wiki["commands"].edit(table)
			last_wiki_update = time()
		else:
			log("Warning: Command Lock timed out on update_commands_wiki() !!")

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
	send_message(f"Welcome to Kaywee's channel {username}! Get cosy and enjoy your stay kaywee1AYAYA <3")
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

		sleep(60*60)

def it_is_wednesday_my_dudes():
	reminder_period = 60*60
	last_pink_reminder = get_data("last_pink_reminder", 0)

	time_since = time() - last_pink_reminder
	if time_since <= reminder_period:
		wait_time = reminder_period - time_since
	else:
		wait_time = 0

	sleep(wait_time)

	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	global authorisation_header 

	while True:
		channel_live.wait() # if channel goes offline, wait for it to come back online
		if date.today().weekday() == 2 and datetime.now().hour >= 6: # if it's wednesday and it's not earlier than 6am
			send_message("On Wednesdays we wear pink. If you want to sit with us type /color HotPink to update your username colour.")
			log("Sent Pink reminder.")
			set_data("last_pink_reminder", time())
		sleep(reminder_period)

def it_is_thursday_my_dudes():
	if not get_data("unpink_sent"):
		sleep(20*60) # wait 20 mins into the stream
		send_message("On Thursdays we wear whatever colour we want. Set your username colour by using /color and sit with us.")
		log("Sent UnPink reminder.")
		set_data("unpink_sent", True)

def it_is_worldday_my_dudes():
	if not get_data("worldday_sent"):
		sleep(10*60) # wait 10 mins into stream
		commands_file.worldday({"display-name":"Timed Event"}) # have to include a message dict param
		set_data("worldday_sent", True)

def wordoftheday_timer():
	if not get_data("wordoftheday_sent"):
		sleep(30*60) # wait 30 mins into stream
		commands_file.wordoftheday({"display-name":"Timed Event"}) # have to include a message dict param
		set_data("wordoftheday_sent", True)

def ow2_msgs():
	while True:
		sleep(random.randint(15*60, 45*60)) # random wait between 15 and 45 mins
		channel_live.wait()
		commands_file.ow2({"display-name": "Timed Event"})

def channel_live_messages():
	global channel_live
	global live_status_checked

	while True:
		live_status_checked.wait() # wait for check_live_status to run once

		if not channel_live.is_set():  # if channels isn't already live when bot starts
			channel_live.wait()        # wait for channel to go live
			send_message("!resetrecord", suppress_colour=True)

		Thread(target=it_is_worldday_my_dudes).start()
		Thread(target=wordoftheday_timer).start()

		# these will start right away if channel is already live
		# or if channel is offline, they will wait for channel to go live then start
		weekday_num = date.today().weekday()
		if weekday_num == 3:
			Thread(target=it_is_thursday_my_dudes).start()
		elif weekday_num == 2:
			Thread(target=it_is_wednesday_my_dudes).start()

		channel_offline.wait() # wait for channel to go offline before running again

def nochat_raid():
	sleep(10)
	send_message(f"@{raider} thank you so much for raiding! Kaywee isn't looking at chat right now (!nochat) but she'll see the raid after the current game.")
	log(f"Sent nochat to {raider} for raiding")

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
		url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id

		# first check total follow count from twitch:
		try:
			data = requests.get(url, headers=authorisation_header).json()
			follower_count = data["total"]
		except Exception as ex:
			log("Exception while requesting followers: " + str(ex))

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

		sleep(10*60)

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

def automatic_backup():
	"""
	Autmatically makes a backup of all bot files once per week. Does not delete old files.
	"""
	
	backup_period  = 86400 * 7 # backup once per 7 days
	check_interval = 60*60     # check once per hour

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

		sleep(60*60) # check once per hour

def update_app_access_token():
	global authorisation_header
	url = "https://id.twitch.tv/oauth2/validate"

	while True:
		try:
			current_token = get_data("app_access_token", None)
			assert current_token is not None

			response = requests.get(url, headers=authorisation_header).json()
			expires_in = response["expires_in"]
		except AssertionError:
			log("No Access Token was found in config.txt. Fetching a new one..")
			expires_in = 0
		except Exception as ex:
			log("Exception when checking App Access Token: " + str(ex))
			expires_in = 0

		if expires_in < 48*60*60: # if token expires in the next 48h
			new_token = get_app_access_token(log)
			set_data("app_access_token", new_token) # get a new one
			authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + new_token}

		sleep(23*60*60) # wait 23 hours

def send_message(message, add_to_chatlog=True, suppress_colour=True):
	"""
	Will also be accessible from the commands file.
	"""

	if message[0] in "/." or suppress_colour:
		bot.send_message(message)
	else:
		bot.send_message("slash me " + message)

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
	check_period = 60*30

	last_lurker_check = get_data("last_lurker_check", 0)

	time_since = time() - last_lurker_check
	if time_since <= check_period:
		wait_time = check_period - time_since
	else:
		wait_time = 0

	sleep(wait_time)

	recently_banned = get_data("recently_banned", [])

	while True:
		known_bots = requests.get(bots_url).json()["bots"]

		# the above returns a list of lists like [["botname", number_of_channels, "something else idk"], [..]]
		# so for each bot in the list, bot[0] is the name; bot[1] is the number of channels it's in.
		# Idk that's just how it comes through ok
		# so this makes it into a dict of {name: numchannels}:
		known_bots = dict([(bot[0], bot[1]) for bot in known_bots]) 

		for _ in range(5): # only update the known_bots list every 5 checks. Reduces api calls and there's a lot of data
			viewers = requests.get(viewers_url).json()["chatters"]["viewers"] # doesn't list broadcaster, vips, mods, staff, admins, or global mods
			for viewer in viewers:
				if viewer not in allowed_bots and viewer in known_bots and known_bots[viewer] > 100 and viewer not in recently_banned:
					send_message(f"/ban {viewer}")
					send_discord_message(f"The following uninvited lurker bot has been banned on Twitch: {viewer}")
					log(f"Banned known bot {viewer} for uninvited lurking.")
					recently_banned.append(viewer)
					if len(recently_banned) > 10:
						recently_banned = recently_banned[:10]
					set_data("recently_banned", recently_banned)
					sleep(3) # just helps space the messages out a bit

			set_data("last_lurker_check", int(time()))
			sleep(check_period)

def send_discord_message(message):
	# don't wanna block up the main thread while the discord bot starts up and sends the message
	p = Thread(target=_send_discord_message, args=(message,)).start()

def _send_discord_message(message):
	#this takes a few seconds and probably shouldn't be used too much LOL
	try:
		# fuck discory.py and it's async bs for making me do this
		if os.name == "nt": # WINDOWS:
			subprocess.run("python discord.py " + message, capture_output=True) # capture_output=True means the output doesn't go to console.. When it exit()s it prints the exception stack lol
		else: # NOT WINDOWS (rpi)
			subprocess.run("python3.9 Discord.py " + message, capture_output=True) # capture_output=True means the output doesn't go to console.. When it exit()s it prints the exception stack lol
	except:
		pass

twitch_emotes = []
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

Thread(target=get_twitch_emotes).start()

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

	if "@robokaywee" in message_lower and user not in bots:
		send_message(f"@{user} I'm a bot, so I can't reply. Try talking to one of the helpful human mods instead.")
		log(f"Sent \"I'm a bot\" to {user}")

	elif commands_file.nochat_on and user not in bots and "kaywee" in message_lower:
		msg_words = [word for word in message_lower.split(" ") if word not in twitch_emotes] # remove emotes
		message_lower = " ".join(msg_words).replace("robokaywee", "") # stitch message back together and remove robokaywee

		if "kaywee" in message_lower:
			send_message(f"@{user} {commands_dict['nochat']['response']}")
			log(f"Sent nochat to {user} in response to @kaywee during nochat mode.")

	elif permission < permissions.Subscriber:
		msg_without_spaces = message_lower.replace(" ", "")
		if any(x in msg_without_spaces for x in ["bigfollows.com", "bigfollows*com", "bigfollowsdotcom"]):
			send_message(f"/ban {user}")
			log(f"Banned {user} for linking to bigfollows")

	# EASTER EGGS:

	msg_lower_no_punc = "".join(c for c in message_lower if c in ascii_lowercase+" ")
	
	if message[0] == "^":
		send_message("^", suppress_colour=True)
		log(f"Sent ^ to {user}")

	elif ayy_re.fullmatch(message_lower):
		send_message("lmao")
		log(f"Sent lmao to {user}")

	elif message == "KEKW":
		send_message("KEKWHD Jebaited")
		log(f"Sent KEKW to {user}")

	elif message_lower in ["hewwo", "hewwo?", "hewwo??"]:
		send_message(f"HEWWO! UwU {get_emote('kaywee1AYAYA')}")
		log(f"Sent hewwo to {user}")

	elif message_lower == "hello there":
		send_message("General Keboni")
		log(f"Sent Kenobi to {user}")

	elif "romper" in message_lower:
		send_message("!romper")
		log(f"Sent romper to {user}")

	elif user == "theonefoster" and message_lower == "*sd":
		shutdown_on_offline = True
		log("Will now shutdown when Kaywee goes offline.")

	elif user == "nightroad2593" and message_lower[:6] == "in ow2":
		log(f"Saved new ow2 prediction: {message_lower}")
		with open("ow2.txt", "a") as f:
			f.write(message + "\n")
	elif user in ["gothmom_", "ncal_babygirl24"] and "lucio" in message_lower:
		send_message("IS UR MAN HERE??")
		log(f"Sent \"Is your man here?\" to {user}")
	elif msg_lower_no_punc == "alexa play despacito":
		send_message("Now playing Despacito by Luis Fonsi.")
		log(f"Now playing Despacito for {user}")
	elif msg_lower_no_punc == "alexa stop":
		send_message("Now stopping.")
		log(f"Stopping Alexa for {user}")
	elif len(message_lower.split()) == 2 and message_lower.split()[0] in ["im", "i'm"]:
		send_message(f"Hi {message.split()[1]}, I'm dad!")
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
	elif msg_lower_no_punc == "youre walking in the woods":
		send_message("There's no-one around and your phone is dead.")
		log(f"Sent Shia (part 1) to {user}")
	elif msg_lower_no_punc == "out of the corner of your eye you spot him":
		send_message("Shia Lebeuf!")
		log(f"Sent Shia (part 2) to {user}")
	elif msg_lower_no_punc in ["modcheck", "mod check"]:
		send_message(":eyes:")
		log(f"Sent ModCheck to {user}")
	#else:
	#	haiku = is_haiku(message_lower)
	#	if haiku:
	#		send_message(f"@{user} That was a haiku!! {' // '.join(haiku)}")
	#		log(f"Sent Haiku to {user}: {str(haiku)}")

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

	write_command_data(force_update_reddit=True)

	success = False
	dropoff = 0.5

	create_bot()

	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + get_data("app_access_token")}

	Thread(target=channel_events,          name="Channel Events").start()
	Thread(target=update_app_access_token, name="Access Token Updater").start()
	Thread(target=update_subs,             name="Subscriber Updater").start()	
	Thread(target=update_followers,        name="Followers Updater").start()
	Thread(target=set_random_colour,       name="Colour Updater").start()
	Thread(target=channel_live_messages,   name="Channel Live Messages").start()
	Thread(target=automatic_backup,        name="Automatic Backup").start()
	Thread(target=play_patiently,          name="Play Patiently").start()
	Thread(target=ban_lurker_bots,         name="Ban Lurker Bots").start()
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

	if user_messages is None:
		user_messages = dict()
	
	# let commands file access key objects:
	# (these can be modified from commands_file and read from here, or vice versa)
	commands_file.bot                = bot
	commands_file.log                = log
	commands_file.get_data           = get_data
	commands_file.set_data           = set_data
	commands_file.nochat_on          = False
	commands_file.usernames          = usernames
	commands_file.subscribers        = subscribers
	commands_file.permissions        = permissions
	commands_file.send_message       = send_message
	commands_file.command_dict       = commands_dict
	commands_file.last_message       = last_message
	commands_file.user_messages      = user_messages
	commands_file.write_command_data = write_command_data

	print("Setup complete. Now listening in chat.")

	while True:
		try:
			#messages = [{"message_type":"privmsg", "display-name":"theonefoster", "message":"!translate en de this is a test!", "badges":["moderator"]}]
			messages = bot.get_messages()
			for message_dict in messages:
				if message_dict["message_type"] == "privmsg": # chat message
					user	= message_dict["display-name"].lower()
					message = message_dict["message"]
					message_lower = message.lower()

					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"{user}: {message}\n")

					if user not in usernames:
						Thread(target=add_new_username,args=(user,)).start() # probably saves like.. idk 50ms? over just calling it.. trims reaction time though
					elif hello_re.fullmatch(message_lower):
						if user.lower() == "littlehummingbird":
							send_message("HELLO MADDIE THIS IS TOTALLY NOT A SASSY MESSAGE BUT HI") # little easter egg for maddie :)
							log("Said Hello to Maddie, but in a totally not-sassy way")
						else:
							message = "!hello" # react as if they used the command

					last_message[user] = message
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

												command_obj["last_used"] = time()
												write_command_data(force_update_reddit=False)
										else:
											log(f"WARNING: tried to call non-command function: {command}")
									else:
										log(f"WARNING: Stored coded command with no function: {command}")
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

										command_obj["last_used"] = time()
										write_command_data(force_update_reddit=False)
									else:
										log(f"WARNING: Stored text command with no response: {command}")
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
									pass # trigger end of stream events?
									
								message = message_dict["message"]
								log(f"NOTICE: {id}: {message}")
								with open("chatlog.txt", "a", encoding="utf-8") as f:
									f.write(f"NOTICE: (msg_id {id}): {message}\n")
						else:
							log(f"NOTICE with msg_id but no message: {str(message_dict)}")
					else:
						log(f"NOTICE with no msg_id: {str(message_dict)}")

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
								send_message(f"OMG {gifter}!! Thank you so much for my gifted sub, you're the best!! <3 <3 {get_emote('kaywee1AYAYA')}")
							elif commands_file.nochat_on:
								send_message(f"@{gifter} thank you so much for gifting a subscription to {recipient}! Kaywee isn't looking at chat right now (!nochat) but she'll see your gift after the current game.")
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
							# comes through as a gifted sub from AnAnonymousGifter ? So might not need this
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: Anon has gifted a subscription to {recipient}!\n")
							subscribers[recipient] = {"gifter_name":"AnAnonymousGifter", "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "raid": # RAID
							raider = message_dict["msg-param-displayName"]
							viewer_count = message_dict["msg-param-viewerCount"]
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {raider} is raiding with {viewer_count} viewers!\n")
							send_message(f"Wow! {raider} is raiding us with {viewer_count} new friends! Thank you! {get_emote('kaywee1AYAYA')}")
							log(f"{raider} is raiding with {viewer_count} viewers.")
							raid_data = {"raider": raider, "viewers": viewer_count, "time": time()}
							raid_data = str(raid_data).replace(", ", ",") # set_data() replaces ", " with ",\n", but I don't want that to apply to this dict, so removing the space stops it being picked up by that .replace()
							set_data("last_raid", raid_data)

							if commands_file.nochat_on:
								Thread(target=nochat_raid).start() 
								# sends a message in chat after a short delay

						elif message_dict["msg-id"] == "submysterygift":
							gifter = message_dict["login"] # comes as lowercase
							gifts = message_dict["msg-param-mass-gift-count"]

							if gifts != "1":
								log(f"{gifter} has gifted {gifts} subscriptions to the community.")
							else:
								log(f"{gifter} has gifted a subscription to the community.")

						elif message_dict["msg-id"] == "giftpaidupgrade":
							subscriber = message_dict["msg-param-sender-login"] 

							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {subscriber} has continued their gifted sub.\n")
							log(f"{subscriber} has continued their gifted sub.")

							subscribers[subscriber] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for continuing your gifted sub! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for subscribing")
								
						elif message_dict["msg-id"] == "rewardgift":
							pass # for when gifted subs produce extra rewards (emotes) for other chat members

						elif message_dict["msg-id"] == "communitypayforward":
							pass # e.g. <user> is paying forward their gifted sub!
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

				elif message_dict["message_type"] == "clearmsg":
					# single message was deleted
					# e.g {'message_type': 'clearmsg', 'login': 'nacho_888', 'room-id': '', 'target-msg-id': '4e2100ba-f5fe-4338-85a1-cccc191375c7', 'tmi-sent-ts': '1613065616305'}
					target = message_dict["login"] # the user whose message was deleted ?

				elif message_dict["message_type"] == "clearchat":
					# cleared all messages from user
					user_id = message_dict.get("target-user-id", None) # this is the User ID, not the username. It's a str-formatted number.
					# username = get_name_from_user_ID(user_id)
				else:
					with open("verbose log.txt", "a", encoding="utf-8") as f:
						f.write("Robokaywee - unknown message type: " + str(message_dict) + "\n\n")
			dropoff = 1
		except Exception as ex:
			if "An existing connection was forcibly closed" in str(ex):
				dropoff *= 1.5 # exponential dropoff, decay factor 1.5
				log(f"Connection was closed - will try again in {int(dropoff)}s..")
				sleep(dropoff)
				create_bot() # re-create bot object (to reconnect to twitch)
			else:
				log("Exception in main loop: " + str(ex)) # generic catch-all (literally) to make sure bot doesn't crash
