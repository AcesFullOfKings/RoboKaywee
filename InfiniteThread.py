import threading
from time import time, sleep

class InfiniteThread():
	def __init__(self, target=None, name=None, log_func=print, debug=False):
		self.target_func = target
		self.thread_name = name
		self.log_func = log_func
		self.last_error = 0
		self.dropoff = 2
		self.debug=debug

		if self.debug:
			self.log_func(f"{self.thread_name} debug - InfiniteThread created with name {self.thread_name} and target {self.target_func}")

	def catch_exceptions(self, args):
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

		t = threading.Thread(target=self.target_func, name=self.thread_name)
		threading.excepthook=self.catch_exceptions
		t.start()

	def start(self):
		t = threading.Thread(target=self.target_func, name=self.thread_name)
		threading.excepthook=self.catch_exceptions
		t.start()