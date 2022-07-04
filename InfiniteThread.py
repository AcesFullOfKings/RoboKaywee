import threading
from time import time, sleep

def catch_exceptions(args):
	# args[0] = exc_type (e.g. the class representing the exception, e.g. ValueError)
	# args[1] = exc_value (e.g. the Exception object, e.g. a ValueError object )
	# args[2] = exc_traceback - a traceback object
	# args[3] = the Thread object which raised the exception
	
	# pass on the exception handling to the thread itself
	args[3].InfiniteThread._catch_exceptions(args)

class InfiniteThread():
	def __init__(self, target=None, name=None, log_func=print, debug=False):
		self.target_func = target
		self.thread_name = name
		self.log_func = log_func
		self.last_error = 0
		self.dropoff = 2
		self.debug=debug

		threading.excepthook=catch_exceptions

		if self.debug:
			self.log_func(f"{self.thread_name} debug - InfiniteThread created with name {self.thread_name} and target {self.target_func}")

	def _catch_exceptions(self, args):
		if self.last_error < time() - (self.dropoff*3): # reset dropoff after a while
			if self.debug:
				self.log_func(f"{self.thread_name} debug - Last exception was at {self.last_error} - resetting dropoff to 1")
			self.dropoff = 1

		self.last_error = time()
		self.dropoff *= 2
		timeout = self.dropoff
		
		if self.debug:
			self.log_func(f"{self.thread_name} debug - dropoff is now {self.dropoff}")

		self.log_func(f"Exception in {self.thread_name}: {args[0].__name__} - {str(args[1])} - sleeping for {round(timeout, 1)}s..")
		sleep(timeout)

		self.recreate_thread()

	def start(self):
		self.recreate_thread()

	def recreate_thread(self):
		t = threading.Thread(target=self.target_func, name=self.thread_name)
		t.InfiniteThread = self # "if it's stupid but it works, it's not stupid"
		t.start()