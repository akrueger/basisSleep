#!/usr/bin/env python
import sys
import re
from StringIO import StringIO # just need this one method
import BaseHTTPServer
import urllib2
import urllib
import os
import os.path
from cookielib import CookieJar, MozillaCookieJar, LWPCookieJar
import json
import csv #for csv conversion
import datetime
import time # time.time() in RetrieveJsonOrCached and Login(), time.sleep in Sync, 
import calendar
import optparse

#  local imports
from configfile import Config
from config2 import Config2

qw = lambda(s): tuple(s.split) # convenience function
#def qw(s):	return tuple(s.split())

DEBUG = 0 # set to 1 to turn on

CFG_FILEPATH = 'BasisRetriever.cfg' # user-settable advanced config
STATE_FILEPATH = 'app_state.json' # application state

# The values below are only for initializing config file.
DEFAULTS = {
	# All these are either internal or set in the ui
	'loginid':'', 
	'login_timestamp':0,
	'passwd':'', 
	'enc_passwd':'', 
	'savedir':'', 
	#'userid':'', 
	'save_pwd':0,
	#'json_csv':'csv', 
	'month':(0,'Jan'), 
	'year':2015, 
	'session_token':'', 
#	'act_metr':1, 
#	'jsondir':'json', 
}
	
class BasisRetr:
	"""The main entry points, once a BasisRetr object has been created, are: 
	1) GetDayData()-- download metrics, activity, sleep data for a single day from the basis website and save it
	2) GetActivityCsvForMonth()-- download activity summaries for an entire month
	3) GetSleepCsvForMonth()--download sleep summaries for an entire month."""
	LOGIN_URL = 'https://app.mybasis.com/login'
	METRICS_URL = 'https://app.mybasis.com/api/v1/metricsday/me?day={date}&padding=0&bodystates=true&heartrate=true&steps=true&calories=true&gsr=true&skin_temp=true&air_temp=true'
	ACTIVITIES_URL ='https://app.mybasis.com/api/v2/users/me/days/{date}/activities?expand=activities&type=run,walk,bike,sleep'
	SLEEP_URL = 'https://app.mybasis.com/api/v2/users/me/days/{date}/activities?expand=activities&type=sleep'
	SLEEP_EVENTS_URL = 'https://app.mybasis.com/api/v2/users/me/days/{date}/activities?type=sleep&event.type=toss_and_turn&expand=activities.stages,activities.events'

	def __init__(self, loadconfig = None):
		# create config info
		self.app_state = Config(defaults=DEFAULTS, fpath=STATE_FILEPATH)
		self.has_error = False
		if loadconfig:
			self.app_state.Load()
		else:
			# if config file doesn't exist, save the defaults loaded above
			self.app_state.Save() #saves 
	
		self.CFG= Config2()
		err_text = self.CFG.Parse(CFG_FILEPATH)
		if err_text:
			print 'Config file read error: '+err_text
		# url opener for website retrieves
		self.cj = MozillaCookieJar(self.CFG.cookie_filename)
		self.session_cookie = None
		if os.path.exists(self.CFG.cookie_filename):
			self.cj.load()
			self.CheckSessionCookie() # set session cookie if it exists and hasn't expired
		# need to use build_opener to submit cookies and post form data
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))

	def GetDayData(self, yr, mo, day, typ, save_csv, override_cache = False, act_metr= True):
		"""Main entry method for getting a day's worth of data, formatting, then saving it.  typ is the type of data: metrics, activities, or sleep.  Data is always saved in json format, but if save_csv is True, save to csv as well as json. override_cache ignores any already downloaded json.  act_metr, if True, saves sleep and activity state along with metrics."""
		date = self.YrMoDyToString(yr, mo, day)
		# Need yesterday's date to get sleep events for a given calendar day. This is because sleep events, as downloaded from the Basis Website, start from the prior evening, when you actually went to sleep.
		ydate = self.YrMoDyToString(*self.GetYesterday(yr, mo, day))
		
		self.Status("Checking Login")
		if not self.CheckLogin(): # ensure we're logged in
			return False
			
		self.Status("getting {} for {}".format(typ,date))
		# figure out which data to get
		data = None
		
		# automatically override cache if day is incomplete (doesn't have 24 hrs of data)
		if not self.DayMetricsJsonIsComplete(date):
			override_cache = True
	
		# if needed, download json data from website and save to file
		if typ == 'metrics':
			mjdata = self.RetrieveJsonOrCached(date, 'metrics', override_cache)
			if not mjdata: # there was an error
				return False

			### MOVE THIS ERROR CHECKING INTO THE ABOVE METHOD
			if type(mjdata) == str or mjdata == None: # simple error checking
				self.Status('OnGetDayData: Metrics json conversion failed.')
				return False
			# also load up actities
		if typ == 'activities' or act_metr:
			ajdata = self.RetrieveJsonOrCached(date, 'activities', override_cache)
			if type(ajdata) == str or ajdata == None: # simple error checking
				self.Status('OnGetDayData: Activities json conversion failed.')
				return False
		if typ == 'sleep' or act_metr:
			sjdata = self.RetrieveJsonOrCached(date, 'sleep', override_cache)
			if type(sjdata) == str or sjdata == None: # simple error checking
				self.Status('OnGetDayData: Sleep json conversion failed.')
				return False
			if act_metr: # add yesterday's sleep data
				sjdata2= self.RetrieveJsonOrCached(ydate, 'sleep')
		
		# Next, turn the list of python objects into a csv file.
		# If asked to (via act_metr), collect sleep and activity type, then add them to each timestamp.
		cdata = None
		if save_csv:
			if typ == 'activities' or act_metr:
				act_list = self.JsonActivitiesToList(ajdata)
				cdata = self.CreateCSVFromList(self.CFG.csv.activity_colnames, act_list)
			if typ == 'sleep' or act_metr:
				sleep_evts_list = self.JsonSleepEventsToList(sjdata)
				cdata = self.CreateCSVFromList(self.CFG.csv.sleep_evt_colnames, sleep_evts_list)
				if act_metr:
					# prepend yesterday's sleep events as they may start before midnight.
					sleep_evts_list[:0] = self.JsonSleepEventsToList(sjdata2)
			if typ == 'metrics':
				if u'error' in mjdata:
					err = mjdata[u'error']
					self.Status("HTTP response error ({}, # {}): {}".format(err[0],mjdata[u'code'], err[1]))
					return
				metrics_list = self.JsonMetricsToList(mjdata)
				if act_metr: # add activities to metrics               
					self.AddActivityTypeToMetrics(metrics_list, act_list, sleep_evts_list)
					header = self.CFG.csv.metrics_colnames + self.CFG.csv.activity_type_colnames
				else:
					header = self.CFG.csv.metrics_colnames
				cdata = self.CreateCSVFromList(header, metrics_list)
		
		# If we were able to make a csv file, save it.
		if cdata:
			fpath = self.PathForFile(date, typ, 'csv')
			fname = os.path.split(fpath)[1]
			self.SaveData(cdata, fpath)
			self.Status("Saved "+typ+" csv file "+fname)
		return True # success

	def PathForFile(self, dt, typ, fmt):
		cfname = self.CFG.day_fname_template.format(date=dt, typ=typ, fmt=fmt)
		folder = self.app_state.savedir if fmt =='csv' else self.GetJsonStorageDir()
		fpath = os.path.join(os.path.abspath(folder), cfname)
		return fpath

	##
	##	TODO: How deal with sync before you registered with Basis?
	##
	def Sync(self, do_csv, override_cache, act_metr=True, callback = None):
		"""Secondary entry point. Catch up to current day. Downloads any missing or incomplete days, going back self.app_state.sync days."""
		# download what we have for today.  It won't be complete, but you can at least get the data.
		today = datetime.date.today()
		yr, mo, dy = today.year, today.month, today.day
		file_count = 0 # tallly # of files actually changed
		if not self.CheckLogin(): # make sure we're logged in correctly before starting
			return
		for days in range(self.CFG.sync_days):
			# see if files already exists
			dt = self.YrMoDyToString(yr, mo, dy)
			self.Status('Sync: checking '+dt)
			fpath = self.PathForFile(dt, 'metrics', 'csv')
			# if file doesn't exist, then found = false, and/or break
			if not os.path.isfile(fpath) or not self.DayMetricsJsonIsComplete(dt): # download day.
				# if override_cache is True, then will always re-download all days.  Don't let that happen.
				if not self.GetDayData(yr, mo, dy, 'metrics', do_csv, override_cache = False, act_metr = act_metr):
					return # quit if problem
				file_count += 1
				if callable(callback): # callback (if available) to UI manager to prevent freeze
					callback(yr, mo, dy) # allow
			# loop change: yesterday.
			yr, mo, dy = self.GetYesterday(yr, mo, dy)
		# Done. Let user know.
		self.Status('Sync done; {} files updated'.format(file_count if file_count > 0 else 'no'))

	def CheckLogin(self):
		"""Check to see if Login is needed; if so, then log in. """
		elapsed_hr = (time.time() - self.app_state.login_timestamp)/3600
		if self.CheckSessionCookie() and self.app_state.session_token and elapsed_hr < self.CFG.login_timeout_hrs:
			success = True
		else:
			try:
				self.Login()
				success = True
			except Exception, v:
				self.Status('Login difficulty: '+`v[0]`)
				success= False
		if success:
			self.app_state.login_timestamp = time.time()
		return success
		
		
	def Login(self, login = None, passwd = None):
		"""Log in to basis website to get session (access) token via cookie. If loginid and password specified, store them in config."""
		if login:
			self.app_state.loginid = login
		if passwd:
			self.app_state.passwd = passwd

		form_data = { # these are all required by the basis website.
			'next': 'https://app.mybasis.com',
			'submit': 'Login',
			'username': self.app_state.loginid,
			'password': self.app_state.passwd}
		enc_form_data = urllib.urlencode(form_data)
		if DEBUG:
			cs = "\n".join([`c` for c in self.cj])
			print "Attempting to log in with url=",BasisRetr.LOGIN_URL, "form data=",enc_form_data, "cookies=",cs

		result = self.JsonHTTPRequest(BasisRetr.LOGIN_URL, data = enc_form_data, json_convert = False)

		#$ do we need to close f?
		m = re.search('error_string\s*=\s*"(.+)"', result, re.MULTILINE)
		if m:
			raise Exception(m.group(1))

		
		# make sure we got the access token
		if not self.CheckSessionCookie():
			self.Status("Just logged in but didn't find access token in cookies.")
		else:
			self.Status('Logged in.')
			self.app_state.login_timestamp = time.time() # remember when logged in for timeout purposes
		
	def CheckSessionCookie(self):
		"""If there's an unexpired session cookie, return it."""
		val = None
		for cookie in self.cj:
			if cookie.name == 'access_token' and not cookie.is_expired():
				val = cookie.value
		self.app_state.session_token = val
		return val
		
		
	########################################
	##
	##		Retrieve (raw) json files from website
	##
	def RetrieveMetricsJsonForDay(self, date):
		# Form the URL
		url = BasisRetr.METRICS_URL.format(date=date)
		return self.GetJsonData(url)
		
	def RetrieveActivitiesJsonForDay(self, date):
		url = BasisRetr.ACTIVITIES_URL.format(date = date)
		return self.GetJsonData(url)

	def RetrieveSleepSummaryJsonForDay(self, date):
		url = BasisRetr.SLEEP_URL.format(date=date)
		return self.GetJsonData(url)

	def RetrieveSleepEventsJsonForDay(self,date):
		url = BasisRetr.SLEEP_EVENTS_URL.format(date=date)
		return self.GetJsonData(url)

	def GetJsonStorageDir(self):
		"""Allow json storage dir to be absolute or relative (to csv dir) path."""
		if os.path.isabs(self.CFG.json_dir):
			return self.CFG.json_dir
		else:
			return os.path.join(os.path.abspath(self.app_state.savedir), self.CFG.json_dir)

	
	def RetrieveJsonOrCached(self, date, typ, user_override_cache = False, only_cache = False):
		"""If json file exists in json dir, then just read that.  Otherwise, download from basis website.  If override_cache is set, always download from website."""
		jdata = None
		# if file exists and we've said via UI, "don't override the cache", then read json from cache
		fpath = self.PathForFile(date, typ, fmt='json')
		if os.path.isfile(fpath) and not user_override_cache:
			with open(fpath, "r") as f:
				data = f.read()
				jdata = json.loads(data)
		elif not only_cache: # then OK to retrieve data from website
			try:
				if typ == 'metrics':
					jdata = self.RetrieveMetricsJsonForDay(date)
				elif typ == 'activities':
					jdata = self.RetrieveActivitiesJsonForDay(date)
				elif typ == 'sleep':
					jdata = self.RetrieveSleepEventsJsonForDay(date)
				elif typ == 'sleep_summary':
					jdata = self.RetrieveSleepSummaryJsonForDay(date)
			except Exception, v:
				err_msg = 'Problem retrieving data. '+`v[0]`
				self.ReportProblem(err_msg)
				return
			# make sure directory exists
			if not os.path.isdir(self.GetJsonStorageDir()):
				os.makedirs(self.GetJsonStorageDir())
			self.SaveData(json.dumps(jdata), fpath)
		return jdata
	
	def DayMetricsJsonIsComplete(self, dt, jdata = None):
		"""Check to see if all 1440 minutes of the day have been downloaded into json file."""
		fpath = self.PathForFile(dt, 'metrics', 'json')
		if not os.path.isfile(fpath):
			return False
		if jdata is None:
			jdata = self.RetrieveJsonOrCached(dt, 'metrics', only_cache = True)
		try:
			result = None not in jdata['metrics']['calories']['values'] if jdata and 'metrics' in jdata else False
		except Exception, v:
			self.Status('Day Metrics Complete test problem: '+v[0]+". Returning False")
			result = False
		return result


	def GetJsonData(self, url):
		"""Download data from Basis website (on cache failure or if user forced)."""
		jresult = self.JsonHTTPRequest(url)
		
		# callback (if available) to UI manager to ensure it doesn't freeze
		if hasattr(self, 'FreezePrevention'):
			self.FreezePrevention()
			
		if 'code' in jresult and jresult['code'] == 401: # unauthorized.  try logging in
			if self.has_error:
				raise Exception("Auth Error during login (HTTP error {}): {}. Quitting.".format(jresult['code'],jresult['error']))
				self.cj.clear() # empty cookies 
				return
				
			self.Status("Logging in for new session token.")
			self.has_error = True
			self.Login()
			jresult = self.JsonHTTPRequest(url)
			
		if 'code' in jresult and jresult['code'] != 200:
			raise Exception("Error during login (HTTP error {}): {}. Quitting.".format(jresult['code'],str(jresult['error'])))
		return jresult


	def JsonHTTPRequest(self, url, data = None, json_convert = True):
		if DEBUG:
			print 'JsonHTTPReq: Trying URL',url
		try:
			f = self.opener.open(url, data) # already was initialized with cookie jar
			result = f.read()
		except urllib2.HTTPError as e:
			reason = BaseHTTPServer.BaseHTTPRequestHandler.responses[e.code]
			result = {'code': e.code, 'error':reason, 'url':url}
			if data:
				result['data'] = data
			return result
		if json_convert:
			json_result = json.loads(result)
			if DEBUG:
				print 'URL result',result if len(result)<=200 else result[:200]+"..."
				print self.CookieJarInfo()
			return json_result
		else:
			return result

	def SaveData(self, data, fpath):
		fname=os.path.split(fpath)[1]
		try:
			fh = file(os.path.abspath(fpath), "w")
			fh.write(data)
		except IOError, v:
			self.Status("Problem saving file "+fname+"\n--Error: "+`v`)
		try: # if problem is on open, then fh doesn't exist.
			fh.close()
		except:
			pass

	################################
	##
	##				Methods for extracting data from json into lists of dicts
	##
	def JsonMetricsToList(self,j):
		result = []
		interval = j['interval'] if 'interval' in j else 60
		if 'endtime' not in j:
			return 
		for i in range((j['endtime'] - j['starttime']) / interval):
			unix_time_utc = j['starttime'] + i*interval
			skin_temp = j['metrics']['skin_temp']['values'][i]
			air_temp = j['metrics']['air_temp']['values'][i]
			heartrate = j['metrics']['heartrate']['values'][i]
			steps = j['metrics']['steps']['values'][i]
			gsr = j['metrics']['gsr']['values'][i]
			calories = j['metrics']['calories']['values'][i]

			# get datetime as string
			date_time = datetime.datetime.fromtimestamp(unix_time_utc).__str__()
			dt, tm = date_time[:10], date_time[11:]
			result.append({'tstamp':unix_time_utc,'datetime':date_time, 'date':dt,'time':tm, 'skin_temp':skin_temp, 'air_temp':air_temp, 'heartrate':heartrate, 'steps':steps, 'gsr':gsr, 'calories':calories})
		return result

	def AddActivityTypeToMetrics(self, metrics_list, activity_list, sleep_list):
		"""Append activity type to each applicable minute of the day.  Assumes each list is monotonically increasing in time. This also presumes that activity and sleep data encompass metrics data."""
		metrics_span = metrics_list[0]['tstamp'], metrics_list[-1]['tstamp']
		# it's possible there were no activities for the day.
		# the below try doesn't do the right thing.  If len == 0, still tries to evaluate [0] and fails
		if type(activity_list) != list:
			print "AddActivityToMetrics: activity list should be array, but instead is string:",`activity_list`[:200]
			return
		if type(sleep_list) != list:
			print "AddActivityToMetrics: sleep events list should be array, but instead is string:",`sleep_list`[:200]
			return
		activity_span = len(activity_list)>0 and (activity_list[0]['start_tstamp'], activity_list[-1]['end_tstamp']) or metrics_span
		sleep_span = len(sleep_list) > 0 and (sleep_list[0]['start_tstamp'], sleep_list[-1]['end_tstamp']) or metrics_span
			
		a_i = 0 # index into activity list
		s_i = 0 # index into sleep events list
		t_i = 0# index into toss_turn sleep events
		# Go through metrics (each minute of the day)
		for mrow in metrics_list:
			if len(activity_list)>0:
				# first, look for the first activity whose start time comes before or at the timestamp
				while a_i < len(activity_list)-1 and mrow['tstamp']> activity_list[a_i]['end_tstamp']:
					# current activity starts before timestamp
					a_i +=1
				# a_i now points to the first activity that starts before current time stamp
				# if we're also before the end of the activity, then note it.
				# activity starts if anytime within the prior minute (therefore the -59)
				if mrow['tstamp'] >= activity_list[a_i]['start_tstamp']-59 and mrow['tstamp'] <= activity_list[a_i]['end_tstamp']:
					mrow['act_type'] = activity_list[a_i]['type']
			else:
				mrow['act_type'] = ""
			
			if len(sleep_list) > 0:
				# next, advance the sleep event pointer to the right place.
				while s_i < len(sleep_list)-1 and mrow['tstamp']> sleep_list[s_i]['end_tstamp']-59:
					# current activity starts before timestamp
					s_i +=1
				
				# advance sleep events counter until timestamp falls after the next sleep event start time.
				# ignore toss_and_turn events
				while t_i < len(sleep_list)-1 and (mrow['tstamp']> sleep_list[t_i]['start_tstamp'] or sleep_list[t_i]['type'] != 'toss_and_turn'):
					t_i += 1

				# options here are to reuse the type column above. That makes for smaller files
				# instead, we're using a separate field.  This makes it easier for the user
				# to filter out "all sleep events" or "all activities" without having to enumerate them.
				# could also use separate field for toss_and_turn events
				if sleep_list[t_i]['type'] == 'toss_and_turn' and sleep_list[t_i]['start_tstamp'] == mrow['tstamp']:
					mrow['toss_turn'] = sleep_list[t_i]['type']
				else:
					mrow['toss_turn'] = ""
					
				if mrow['tstamp'] >= sleep_list[s_i]['start_tstamp']-59 and mrow['tstamp'] < sleep_list[s_i]['end_tstamp']:
					mrow['sleep_type'] = sleep_list[s_i]['type']
				else:
					mrow['sleep_type'] = ""

	def JsonActivitiesToList(self, j):
		"""Turn Json-structured activity data into a list of dict, each dict being an activity"""
		presult = []
		if 'content' not in j or 'activities' not in j['content']:
			err = "Err in BasisRetr::JsonActivitiesToList: didn't get activities, got",j
			print "NoActivities",err
			return err
		activities = j['content']['activities']
		for i in range(len(activities)):
			a = activities[i]
			start_timestamp = a['start_time']['timestamp']
			start_dt = datetime.datetime.fromtimestamp(start_timestamp).__str__()
			start_date, start_time = start_dt[:10], start_dt[11:]
			end_timestamp = a['end_time']['timestamp']
			end_dt = datetime.datetime.fromtimestamp(end_timestamp).__str__()
			end_date, end_time = end_dt[:10], end_dt[11:]
			steps = 'steps' in a and a['steps'] or 0
			# finally, add info to tag metrics with activity type
			presult.append({'start_tstamp':start_timestamp, 'start_dt':start_dt, 'end_dt':end_dt,'start_date':start_date, 'start_time':start_time,'end_tstamp':end_timestamp, 'end_date':end_date, 'end_time':end_time, 'type':a['type'], 'calories':a['calories'],'actual_seconds':a['actual_seconds'], 'steps':steps})
		return presult

	def JsonSleepEventsToList(self, j):
		"""Sleep events are more complicated and nested. Within [0..n] activities, there are [0..n] stages, each with a start and end time.  There are also [0..n] events (I think only "toss_and_turn").  Both stages and events are parsed below, then combined and sorted by time via tuples.  The tuples are then turned into csv rows."""
		presult = [] # python array as needed for adding stages to metrics
		if 'content' not in j or 'activities' not in j['content']:
			err = "Err in BasisRetr::JsonSleepEventsToList: didn't get activities, got",json.dumps(j, indent=2)
			return err
		activities= j['content']['activities']
		# first, get data from "stages"
		result = []
		for i in range(len(activities)):
			a = activities[i]
			if 'stages' not in a:
				err = "Err in BasisRetr::JsonSleepEventsToList: didn't get stages, got",json.dumps(j, indent=2)
				return err
				
			stages = a['stages']
			for j in range(len(stages)):
				s = stages[j]
				start_timestamp = s['start_time']['timestamp']				
				start_dt = datetime.datetime.fromtimestamp(start_timestamp).__str__()
				start_date, start_time = start_dt[:10], start_dt[11:]
				end_timestamp = s['end_time']['timestamp']				
				end_dt = datetime.datetime.fromtimestamp(end_timestamp).__str__()
				end_date, end_time = end_dt[:10], end_dt[11:]
				duration = s['minutes']
				
				presult.append({'start_tstamp':start_timestamp, 'start_date':start_date, 'start_time':start_time,'start_dt':start_dt, 'end_dt':end_dt,'end_tstamp':end_timestamp, 'end_date':end_date, 'end_time':end_time, 'duration':duration,'type':s['type']})
				
			# next is toss-turn events
			events = a['events']
			for j in range(len(events)):
				e = events[j]
				start_timestamp = e['time']['timestamp']
				start_dt = datetime.datetime.fromtimestamp(start_timestamp).__str__()
				start_date, start_time = start_dt[:10], start_dt[11:]
				
				duration = 0 # The only event is "toss-turn" which always have zero duration
				presult.append({'start_tstamp':start_timestamp, 'start_date':start_date, 'start_time':start_time,'end_tstamp':start_timestamp, 'end_date':start_date, 'end_time':start_time, 'duration':duration,'type':e['type']})
			
			# now, combine events and stages by sorting results by start_timestamp
			presult.sort(key=lambda row: row['start_tstamp'])
		return presult

	def JsonSleepSummaryToList(self, j):
		"""Turn Json-structured sleep event data into a list of dict, each dict being a sleep event"""
		presult = []
		if 'content' not in j or 'activities' not in j['content']:
			err = "Err in BasisRetr::AddActivitiesCSV: didn't get activities, got",json.dumps(j, indent=2)
			return err
		activities = j['content']['activities']
		for i in range(len(activities)):
			# The activity object has basic info: timestamps, calories, duration, heart rate
			a = activities[i]
			
			start_timestamp = a['start_time']['timestamp']
			start_dt = datetime.datetime.fromtimestamp(start_timestamp).__str__()
			start_date, start_time = start_dt[:10], start_dt[11:]
			
			end_timestamp = a['end_time']['timestamp']
			end_dt = datetime.datetime.fromtimestamp(end_timestamp).__str__()
			end_date, end_time = end_dt[:10], end_dt[11:]
			
			# The sleep part of the activity has sleep event durations
			s = a['sleep']
			
			presult.append({'start_tstamp':start_timestamp, 'start_date':start_date, 'start_time':start_time, 'start_dt':start_dt, 'end_dt':end_dt,'end_tstamp':end_timestamp, 'end_date':end_date, 'end_time':end_time, 'calories':a['calories'],'actual_seconds':a['actual_seconds'], 'heart_rate':a['heart_rate']['avg'], 'rem_minutes':s['rem_minutes'], 'light_minutes':s['light_minutes'], 'deep_minutes':s['deep_minutes'], 'quality':s['quality'], 'toss_and_turn':s['toss_and_turn'], 'unknown_minutes':s['unknown_minutes'], 'interruption_minutes':s['interruption_minutes']}) 
		return presult

	#############################
	##
	##			Turn array of python objects into csv text
	##
	def CreateCSVFromList(self, col_names, pdata):
		# Create csv "file" (actually string) using DictWriter
		csv_file = StringIO()
		writer = csv.DictWriter(csv_file, lineterminator=self.CFG.csv.lineterminator, 
			fieldnames = col_names, extrasaction='ignore')
		writer.writerow(dict((fn,fn) for fn in col_names))
		for row in pdata:
			writer.writerow(row)
		result = csv_file.getvalue() # grab value before closing file
		csv_file.close()
		return result
		
	##############################
	##
	##				Retrieve summary data for an entire month
	##
	def GetActivityCsvForMonth(self, yr, mo, start = 1, end = None, override_cache = False):
		"""Retrieve json files and convert into csv.  Append all CSVs into a single file."""
		
		days_in_month, end = self.GetMonthConstraint(yr, mo)
		if end ==0:
			self.Status("Future month, no data retrieved")
			return
		result = []
		for dy in range(start,end+1):
			date = '%s-%02d-%02d' % (yr, mo, dy)
			self.Status("Getting activity data for "+date)
			
			# download the json file
			jresult = self.RetrieveJsonOrCached(date, 'activities')
			if not jresult: # error
				return
			result.extend(self.JsonActivitiesToList(jresult))
			
		csv_data = self.CreateCSVFromList(self.CFG.csv.activity_colnames, result)
		fname = self.CFG.mo_fname_template.format(yr=yr, mo=mo, typ='activities')
		csv_path = os.path.join(os.path.abspath(self.app_state.savedir), fname)
		self.SaveData(csv_data, csv_path)
		fname = os.path.split(csv_path)[1]
		self.Status('Saved activities as '+fname)
		return result

	def GetSleepCsvForMonth(self, yr, mo, start = 1, end = None):
		"""Retrieve json files and convert into csv.  Append all CSVs into a single file."""
		days_in_month, end = self.GetMonthConstraint(yr, mo)
		# default to the number of days in the month, or today, whichever is later.
		if end ==0:
			self.Status("Future month, no data retrieved")
			return
		result = []
		for dy in range(start,end+1):
			date = '%s-%02d-%02d' % (yr, mo, dy)
			self.Status("Getting sleep events for "+date)
			jresult = self.RetrieveJsonOrCached(date, 'sleep')
			if jresult: # ignore dates for which we don't have data (or incomplete data if cfg.only_complete
				result.extend(self.JsonSleepSummaryToList(jresult))
			
		fname = BasisRetr.MO_FNAME_TEMPLATE.format(yr=yr, mo=mo, typ='sleep')
		csv_data = self.CreateCSVFromList(self.CFG.csv.sleep_colnames, result)
		csv_path = os.path.join(os.path.abspath(self.app_state.savedir), fname)
		self.SaveData(csv_data, csv_path)
		fname = os.path.split(csv_path)[1]
		self.Status('Saved sleep events to '+fname)
		return result


	def GetMonthConstraint(self, yr, mo):
		"""If today is before the end of the current month, then constrain end-date.  No need to try and retrieve dates in the future."""
		days_in_month = calendar.monthrange(yr, mo)[1]
		end_of_month = datetime.date(yr, mo, days_in_month)
		today = datetime.date.today()
		if yr > today.year or yr == today.year and mo > today.month:
			end = 0
		elif today < end_of_month:
			end = today.day # don't collect data for the future.
		else: # go to end of month
			end = days_in_month
		return days_in_month, end
		

	##############################
	##
	##				General Helpers
	##
	def GetYesterday(self, yr, mo, day):
		"""When was yesterday?"""
		
		tday, tmo, tyr = day-1, mo, yr
		
		if tday <1: # previous month
			tmo -= 1
			if tmo < 1: # previous year
				tyr -= 1
				tmo = 12
			# once we adjusted the month, find the last day of that month 
			tday = calendar.monthrange(tyr, tmo)[1]
		return tyr, tmo, tday

	def YrMoDyToString(self, yr, mo, dy):
		return self.CFG.date_fmt.format(yr=yr, mo=mo, day=dy)
	# the following is used only in BasisAnalyzer.py
	
	def MetricsCsvFileExists(self, d):
		"""True if metrics file exists for given date d"""
		return os.path.isfile(self.PathForFile(d, 'metrics', fmt='csv'))
	
	def OnClose(self):
		"""Save Config file and file-based cookiejar"""
		self.app_state.Save()
		try: # there seems to be a problem with cookie timestamp out of range of epoch on OS-X (10.6.8). Solution right now is to just ignore.
			self.cj.save(self.CFG.cookie_filename)
		except Exception, v:
			print "Problem Saving cookies on exit:", `v`
					
	def Status(self, s):
		"""Placeholder for owner to override (e.g., show messages in status bar)"""
		print datetime.datetime.now(),"Status:",s

	def ReportProblem(self, err_msg):
		self.Status(err_msg)
		sys.stderr.write(err_msg)

	def CookieJarInfo(self):
		"""For debug purposes."""
		return 'CookieJar =',`["({}={}), ".format(c.name,c.value) for c in self.cj]`

##
##		End BasisRetr
##
#######################
##
## The following two are for debug support
##
import pprint
def ppp(object):
	"""debugging support: pretty print any object"""
	pprint.PrettyPrinter().pprint(object)

def pp2(o):
	for k,v in o.__dict__.items():
		if type(v) != list:
			print k,"=>",v


def execute(options):
	"""parse options and run basis_retr."""
	# before we start, we must have a date
	date_match= re.search("^(\d{4})-(\d\d)(-(\d\d))?$", options.date or "")
	
	if date_match:
		yr, mo, x, day = [x and int(x) for x in date_match.groups()]
	else:
		print "Date needs to be specified on command line-- couldn't find one. Stopping."
		return

	# default is to use cached params, specify --nocache option to not use them.
	b = BasisRetr(not options.nocache)
	# place certain options into config
	for o in qw("savedir loginid loginid passwd type"):
		if hasattr(options, o):
			val = getattr(options,o)
			if val:
				setattr(b.cfg, o, val)

	method = options.type
	# metric day with added activities columns, convert it to the basic method and set "add activities" flag.
	if method == 'dma'or method == 'mda': 
		method = 'dm'
		act_metr = 1

	do_csv = b.cfg.json_csv == 'csv'

	# for day metrics and day sleep, make sure date includes a day
	if 'd' in method and not day:
		print "Got month and year in date. Didn't get day, instead got ",options.date, " Stopping."
		return

	# method letters are dm=day metrics, ds = day sleep, ma = month activities, ms = month sleep. 
	# allow for dyslexia	
	if method == 'md' or method == 'dm':
		b.GetDayData(yr, mo, day, 'metrics', do_csv, options.nocache, act_metr)

	elif method == 'ds' or method == 'sd':
		b.GetDayData(yr, mo, day, 'sleep', do_csv, options.nocache)
		
	elif method == 'ma' or method == 'am':
		b.GetActivityCsvForMonth(yr, mo, override_cache =options.nocache)
		
	elif method == 'ms' or method == 'sm':
		b.GetSleepCsvForMonth(yr, mo) ##$$ no override_cache option

	#pp2(b.cfg)
	b.OnClose() # save config data
	

if __name__ == "__main__":
	# allow immediate display of console output
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
	p = optparse.OptionParser()
	#options: email, password, type, addactivities, datestring, usecache, savedir, save_pwd
	p.add_option("-l", "--login_id", dest="loginid", help="Login ID (email) for basis Website")
	p.add_option("-p", "--password", dest="passwd", help="Login ID (email) for basis Website")
	p.add_option("-t", "--type", help="Data type: dm (or day_metrics), dma (or day_metrics_activities-- DEFAULT), ds (or day_sleep), ma (or months_activity), ms (or months_sleep)", default = 'dma')
	p.add_option("-d", "--date", help="Date: YYYY-MM-DD for day types, YYYY-MM for month types")
	p.add_option("-C", "--nocache", action='store_true', help="Save email, password (scrambled), savedir to a file so you don't have to specify them for each command", default = False)
	p.add_option("-s", "--savedir", help="Destination directory for retrieved files")
	p.add_option("-w", "--save_pwd", dest="savepwd", action='store_true',help="Save password to cache along with other data.", default = False)
	p.add_option("-V", "--no_csv", dest="json_csv", action="store_const", const="json",help="Normally data is converted to and saved as csv in addition to (raw) json. With -V, only json is stored.", default = 'csv')
	p.add_option("-j", "--jsondir", help="directory to store (raw) json data.  A relative path converts to a subdir beneath save_dir.", default = False)
	p.add_option("-o", "--override_cache", action = 'store_true', help="Override any cached json data files-- retrieve data fresh from server.", default = False)
	
	(options, args) = p.parse_args()
	execute(options)
	
""" Version Log
v0: correctly retrieving metrics and activities.  About to abstract out config saver
v1: first try converting activites json file to csv.  Next step is to get many files.
v2: converted csv writing code to work on StringIO instead of file directly.  Also doing a month at a time.
v3: got GetActivityCsvForMonth() as simple function.  Now integrate with basis_retr class.
v4: before refactoring state retention.
v5: saving and loading Config class.  Next step is to incorporate save and load.
v6: updated config class.  Pulled URLs out of functions and into class vars.
v7: (aligned with BasisRetriever v8). Got refactored metrics, activities, and sleep downloading correctly, csv + json.  Also got month of activities downloading correctly.
v8: (aligned with BasisRetriever v9). Created sleep (detail) events download feature. Got status event callback working (so BasisRetriever can show status in status bar). Constraining month summaries to only get data for up to today.
v9: (aligned with BasisRetriever v11, for release 0.2): more cleanup, some data validation before hitting basis's servers
v10: (aligned with BasisRetriever.py v13): refactored json conversion to result in array of python objects, then have a single "convert to csv" method.  This allows us to do additional processing (e.g., tagging metrics rows with activities or sleep) in the python realm, then convert to csv at the end. Also extracts which headers are saved in the csv files.
v11: (aligned with BasisRetriver.py v14): clean up and got monthly summaries working with refactored processing methods.
v12 (aligned with BasisRetriever.py v15): AddActivitiesToMetrics-- now makes activities part of the metrics list.
v13 (aligned with BasisRetriever.py v16): Sleep data integrated. Still need to confirm data is correct.
v14 (aligned with basis_retr.py v17): fixed bug where fail metrics collection if no sleep events for that day.  Also added "cache override" checkbox to allow forcing redownload of json file.
v15 (aligned with BasisRetriever.py v18): Got json display and json dir config working correctly.  Next step is to move the guts of OnGetDayData() into basis_retr.py in prep for command line implementation.  After that, move column names to config file. THen move Config class to separate file.
v16 (aligned with BasisRetriever.py v19): Moved main method for downloading a single day's data into basis_retr.py. Next, move column names to config file. Then move Config class to separate file.
v17 (also BasisRetriever.py v20): Column names in config file. Config class is now separate file. Next step is cleanup.
v18 (also BasisRetriever.py v21): Got initial command line version running.  Still need to test out options thoroughly.
v19 (also BasisRetriever.py v22): command line data retrieval tested and all versions seem to be working.  Added logic to wait some number of days before allowing cached data to stay. This helps ensure that we don't use cached data for a partially uploaded day.
v20 (also BasisRetriever.py v23): External changes: added explicit jsondir to UI and config. UI now shows only metrics buttons/sizes if Add activities to metrics is checked (as sleep events is superfluous in that case). Fixed bug where no data at all saved for a given month results in no info in UI at all (should be dates and dashes for sizes). Changed "future date" text color to "dark gray"
Internal: packaged CreateDirSelectorWidget into its own method (along with UserSelectDirectory).  Renamed FormatSummaryCell to MakeLabelClickable and made method more generic (can accept arbitrary pathnames or lambdas and arbitrary labels.
v21 (also BasisRetriever.py v24): Cleanup.  Also got datetime working as default fields.  Tightened up month summary data processing.
v22 (for BasisAnalyzer.py v7): Added MetricsCsvFileExists Method to simplify existance test for date csv files.
v23 (only this file): Fixed bug in logic for walking through events when adding columns to day metrics
v24 (only this file), 25 Sept 2014: Updated to be consistent with app.mybasis.com API changes for retrieving metrics.
v25 (with BasisRetriever.py v25), 25 Sept 2014: Added feature to only download day if it's complete.  Also added 'Catch Up' capability- download all days that are missing.
v26 (only this file), 3 Oct 2014: Refactored JsonHTTPRequest. Removed "only complete" feature; instead, added 'make sure day is complete' feature to catchup.  Added DayMetricsJsonIsComplete().  Cleaned out no-longer-used constants.
v27, 4 Oct 2014: Cleaned up CheckLogin(), Login(), CheckSessionCookie().  Refactored several instances of file access into PathForFile().  CatchUp() gracefully handles login problems. DayMetricsJsonIsComplete() is now also used by BasisRetriever.py (v27).
v28, 4 Oct 2014: Introduced (non-working) config2 version of user config params.  Removed code around userid as Basis website doesn't seem to use it anymore.  Changed CatchUp to SyncCleaned up reporting/Status display from Catchup.  Cleaned up comments.
v29, 18 Apr 2015: Cleanup before v0.5 update.
v30, 23 Apr 2015 (with BasisRetriever.py v32): Added config2.py for managing user-settable parameters (BasisRetriever.cfg) and removed several constants. Changed status message text to show filenames, not entire file path.
v31 (with BasisRetriever.py v33), 25 April 2015: Changed json_csv to config item in BasisRetriever.cfg (was in UI).  Capability remains for command line switch to only download json data.
"""