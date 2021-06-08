#if __name__ == "__main__":
#	exit()

from time import time
import requests
import string

#with open("C:\\Users\\James\\source\\repos\\RoboKaywee\\RoboKaywee\\syllables.json", "r") as f:
#	syllables = dict(eval(f.read()))

def timeuntil(timestamp):
	"""
	Takes a unix timestamp and returns a string representing the time left until that time, in days, hours, minutes, and seconds.
	Return value examples:
		"4 days, 1 hour and 0 minutes"
		"18 hours, 21 minutes and 1 second"
		"50 minutes and 12 seconds"
		"7 seconds"
	"""
	time_left = timestamp - time()

	if time_left <= 0:
		raise ValueError("Cannot calulate timeuntil on a past time.")
	else:
		days = int(time_left // 86400)
		hours = int((time_left % 86400) // 3600)
		mins = int((time_left % 3600) // 60)
		seconds = int(time_left % 60)

		if days > 0:
			ds = "day" if days == 1 else "days"
			hs = "hour" if hours == 1 else "hours"
			ms = "minute" if mins == 1 else "mins"

			return (f"{days} {ds}, {hours} {hs}, and {mins} {ms}")
		elif hours > 0:
			hs = "hour" if hours == 1 else "hours"
			ms = "minute" if mins == 1 else "mins"
			ss = "second" if seconds == 1 else "secs"

			return(f"{hours} {hs}, {mins} {ms}, and {seconds} {ss}")
		elif mins > 0:
			ms = "minute" if mins == 1 else "minutes"
			ss = "second" if seconds == 1 else "secs"
			return(f"{mins} {ms} and {seconds} {ss}")
		else:
			ss = "second" if seconds == 1 else "secs"
			return(f"{seconds} {ss}")

def seconds_to_duration(total_seconds):
	"""
	Takes a unix timestamp and returns a string representing the duration until that time, in days, hours, minutes, and seconds.
	Return value examples:
		"4 days, 1 hour and 0 minutes"
		"18 hours, 21 minutes and 1 second"
		"50 minutes and 12 seconds"
		"7 seconds"
	"""

	if total_seconds <= 0:
		raise ValueError("Seconds cannot be less than zero.")
	else:
		days = int(total_seconds // 86400)
		hours = int((total_seconds % 86400) // 3600)
		mins = int((total_seconds % 3600) // 60)
		seconds = int(total_seconds % 60)

		if days > 0:
			ds = "day" if days == 1 else "days"
			hs = "hour" if hours == 1 else "hours"
			ms = "minute" if mins == 1 else "mins"

			return (f"{days} {ds}, {hours} {hs} and {mins} {ms}")
		elif hours > 0:
			hs = "hour" if hours == 1 else "hours"
			ms = "minute" if mins == 1 else "mins"
			ss = "second" if seconds == 1 else "secs"

			return(f"{hours} {hs}, {mins} {ms} and {seconds} {ss}")
		elif mins > 0:
			ms = "minute" if mins == 1 else "minutes"
			ss = "second" if seconds == 1 else "secs"
			return(f"{mins} {ms} and {seconds} {ss}")
		else:
			ss = "second" if seconds == 1 else "secs"
			return(f"{seconds} {ss}")

def log(s):
	"""
	Takes a string, s, and logs it to a log file on disk with a timestamp. Also prints the string to console.
	"""
	current_time = localtime()
	year   = str(current_time.tm_year)
	month  = str(current_time.tm_mon).zfill(2)
	day    = str(current_time.tm_mday).zfill(2)
	hour   = str(current_time.tm_hour).zfill(2)
	minute = str(current_time.tm_min).zfill(2)
	second = str(current_time.tm_sec).zfill(2)
	
	log_time = f"{day}/{month} {hour}:{minute}:{second}"

	print(s)
	with open("log.txt", "a", encoding="utf-8") as f:
		f.write(log_time + " - " + s + "\n")

def translate(query, dest_lang, source_lang="auto"):
	url = "https://clients5.google.com/translate_a/t"
	params = {"client": "dict-chrome-ex",
		"sl" : source_lang,
		"tl": dest_lang,
		"q": query
		}

	response = requests.get(url, params=params).json()

	return response["sentences"][0]["trans"]

"""
def is_haiku(text):
	words = text.split(" ")
	syls = [syllables.get("".join(c for c in word if c in string.ascii_letters+"'").upper(), None) for word in words]

	if None in syls:
		return False
	else:
#		line1 = line2 = line3 = ""

		current_sum = 0
		pointer = -1 # so it increments to zero

		while current_sum < 5:
			pointer += 1
			try:
				current_sum += syls[pointer]
			except IndexError:
				return False

		if current_sum != 5:
			return False
		
		line1 = " ".join(words[:pointer+1])
		current_sum = 0

		while current_sum < 7:
			pointer += 1
			try:
				current_sum += syls[pointer]
			except IndexError:
				return False

		if current_sum != 7:
			return False

		line2 = " ".join(words[len(line1.split(" ")):pointer+1])
		current_sum = 0

		while current_sum < 5:
			pointer += 1
			try:
				current_sum += syls[pointer]
			except IndexError:
				return False

		if current_sum != 5:
			return False

		line3 = " ".join(words[len(line1.split(" ")) + len(line2.split(" ")):pointer+1])

		if len(words) == pointer + 1:
			return line1, line2, line3
		else:
			return False

def syls(text):
	words = text.split(" ")
	syls = [syllables.get("".join(c for c in word if c in string.ascii_letters+"'").upper(), None) for word in words]

	print(syls)
"""