#!/usr/bin/env/python

# python standard libary imports
import sys, os, pprint
import re
from datetime import date # creating date labels in BasisRetrApp::Populate()
import time #for sleep function
import calendar # Populating month listbox and # days/mo for populating each day
import subprocess # for launching files
import webbrowser # for launching help html file
import urllib
# not used yet: import threading # for downloading days in a thread.

# TK imports for UI
import tkFileDialog # for selecting storage dir
import tkFont #for hyperlink styling of openable files
import ttk
from Tkinter import *
#import wckToolTips as ttip # maybe implement later (http://effbot.org/zone/wcklib-tooltips.htm)

# Local imports
from basis_retr import * # only for instantiating BasisRetr
import helpDialog # simple dialog.

# see if this is a mac. For opening files
try:
	import findertools
except:
	ismac = False
else:
	ismac = True

try:
	import log
	log = log.Log('pyslip.log', log.Log.DEBUG)
except ImportError:
	def log(*args, **kwargs):
			pass
	
def qw(s):
	return tuple(s.split())

__version__ = '0.5'
EMAIL_NAME = 'rg1'
EMAIL_DOMAIN = 'rawds.com'

CFG_COLOR = '#e3e9e3' # background color of config area
MIN_DIR_BOX_WIDTH = 20 # minimum width of directory entry boxes
ACTIVITY_TYPE_INTO_METRICS = True
SHOW_JSON_OR_CSV = 'csv'

class BasisRetrApp(Frame):
	"""Application object and UI"""
	
	YEARS = [`yr` for yr in range(2013,2019)]
	DEFAULT_YEAR = '2015'
	#DEFAULT_JSON_CSV = 'csv'

	def __init__(self, root=None,basepath="/"):
		Frame.__init__(self)

		# UI variables stored here. 
		self.ui = {
				'savedir':StringVar(), 
#				'jsondir':StringVar(),
				'loginid':StringVar(),
				'passwd':StringVar(),
				'month':StringVar(),
				'year':StringVar(),
				'save_pwd':IntVar(),
#				'json_csv':StringVar(),
#				'act_metr':IntVar(),
				'override':IntVar(),
				# not needed anymore? 'only_complete':IntVar(),
			}
		self.LINK_FONT= tkFont.Font(size=9,underline=1)
		self.REGULAR_FONT= tkFont.Font(size=9, underline =0)
		self.SYNC_BUTTON_FONT = tkFont.Font(size=10, weight=tkFont.BOLD)

		self.bretr = BasisRetr(loadconfig = True)
		self.bretr.Status = self.Status
		self.bretr.FreezePrevention = self.FreezePrevention
		self.master.title( "MyBasis Website Data Retriever" )
		self.status_bar = StatusBar(self.master)
		self.CreateWidgets()

		self.SetUiFromConfig() # update UI widgets with saved data
		self.PopulateData() # fill center of screen with file info and action buttons
		self.SetHandlers() # do this after UI is populated
		# Show intro message if save-to directory is blank.
		if len(self.GetUI('savedir')) == 0:
			self.config_frame.toggle() # show config area
			self.toggle_state.set(1)
			self.Status('To start: at the top, enter mybasis login id, password, and csv storage directory.')
		
	def OnClose(self):
		try:
			self.GetConfigFromUI() # save config first.
			self.bretr.OnClose()
			master.destroy()
		except Exception as e: # notify (during development) and force application to close.
			print 'error on close:', e
			master.destroy() 

	def ShowHelp(self):
		"""Open up help.html file in the BasisRetriever /doc folder"""
		path = os.path.realpath(os.path.join(os.path.realpath(get_main_dir()),  "doc", "help.html"))
		p_exists = os.path.isfile(path)
		path2 = os.path.realpath(os.path.join(os.path.realpath(get_main_dir()),  "..", "doc", "help.html"))
		p2_exists = os.path.isfile(path2)
		if not p_exists and not p2_exists:
			errmsg = "No help file at "+path+" or "+path2
			self.Status(errmsg)
		else:
			url = self.path2url(path if p_exists else path2)
			webbrowser.open(url, new = 2)

	def path2url(self, path):
		"""Return file:// URL from a filename. 
		From http://stackoverflow.com/questions/11687478/convert-a-filename-to-a-file-url"""
		path = os.path.abspath(path)
		if isinstance(path, unicode):
				path = path.encode('utf8')
		return 'file:' + urllib.pathname2url(path)
		
	def ShowAbout(self):
		helpDialog.Help(master,
		"""Basis Retriever v{}
Copyright (c) 2015, Rich Knopman

This application may be modified and redistributed
under the BSD license. See License.txt for specifics.""".format(__version__))
		
	############################
	##
	##		Primary methods for Creating widgets in the UI
	##
	def CreateWidgets(self):
		self.dir_text = []
		# top row: config toggle and some action buttons
		config1_frame = Frame(self.master)
		config1_frame.pack(side=TOP,fill=X)
		self.toggle_btn=self.CreateTopRowWidgets(config1_frame)

		# toggleframe needs to know about button so can manage its state if need be.
		self.config_frame = ToggleFrame(self.master)
		self.config_frame.pack(side=TOP, fill=X,expand=1)
		self.toggle_btn.bind("<Button-1>", self.config_frame.toggle)
		
		# 1st config row: directory select for saving data
		fr= Frame(self.config_frame.subFrame, bg=CFG_COLOR)
		self.config1_frame =fr
		fr.pack(side=TOP,fill=X, expand=1)
		self.CreateRow1ConfigWidgets(fr)
		# 2nd row: more config
		fr= Frame(self.config_frame.subFrame, bg=CFG_COLOR)
		self.config2_frame = fr
		fr.pack(side=TOP,fill=X, expand=1)
		self.CreateRow2ConfigWidgets(fr)
		
		# Left-hand Column: Month-Year selectors
		moyr_frame = Frame(self.master)
		moyr_frame.pack(side=LEFT, fill=Y)
		self.AddYearSelector(moyr_frame)
		self.AddMonthSelector(moyr_frame)
		
		# main area: table for data and buttons to collect it
		self.data_frame = Frame(self.master) 
		self.data_frame.pack(side = TOP, fill=Y)
		self.config_frame.toggle() # hide config area
		
	def	CreateTopRowWidgets(self, parent):
		"""Create Config toggle, sync button, month summaries, about and help."""
		photo=PhotoImage(file="icon_16_gear.gif")
		# ttk's checkbutton with 'Toolbutton' style has 2 states, which is what we want.
		self.toggle_state = IntVar()
		b = ttk.Checkbutton(parent, image=photo, style='Toolbutton', variable = self.toggle_state)
		b.pack(side=LEFT)
		b.image = photo
		self.AddSyncButton(parent, side=LEFT)
		self.AddSummaryButtons(parent, side=LEFT)
		
		# Info buttons on the right: help and about
		Button(parent, text="?", command = self.ShowHelp, padx=5).pack(side=RIGHT, ipadx=5, padx=10)
		Button(parent, text="About", command = self.ShowAbout, padx=5).pack(side=RIGHT, ipadx=5, padx=10)
		return b # allow caller to set handler
		
	def CreateRow1ConfigWidgets(self, parent):
		"""Create Login ID and password."""
		Label(parent, text='Login ID', padx=5, bg=CFG_COLOR).pack( side=LEFT)
		loginid_text = Entry(parent, width=15,  # path entry
			textvariable = self.ui['loginid'])
		loginid_text.pack(side=LEFT, fill=X)

		Label(parent, text='Password', padx=5, bg=CFG_COLOR).pack( side=LEFT)
		passwd_text = Entry(parent, width=10,  show="*",
			textvariable = self.ui['passwd'])
		passwd_text.pack(side=LEFT, fill=X)
		Checkbutton(parent, text='Save', variable=self.ui['save_pwd'], bg=CFG_COLOR, padx=5).pack(side=LEFT)
		# override cache
		Checkbutton(parent, text='Override cache', variable=self.ui['override'], bg=CFG_COLOR, padx=5).pack(side=LEFT)
		
	def	CreateRow2ConfigWidgets(self, parent):
		
		""" expect no longer needed.  Remove when this is confirmed.
		# json/csv selector
		Label(parent, text='Show ', bg=CFG_COLOR).pack(side=LEFT)
		json_csv_option = OptionMenu(parent, self.ui['json_csv'], *['json', 'csv'])
		json_csv_option.pack(side=LEFT)
		json_csv_option.config(bg=CFG_COLOR)
		"""
		# Directory selection
		self.dir_text = self.CreateDirSelectWidget(parent, 'savedir', 'CSV Dir')

		#### expect no longer needed.  Remove when this is confirmed.
		#self.act_metr_check = Checkbutton(parent, text='Acty/sleep into metrics', variable=self.ui['act_metr'], command = self.OnUIChange, bg=CFG_COLOR)
		#self.act_metr_check.pack(side=LEFT)
		#self.jsondir_text = self.CreateDirSelectWidget(parent, 'jsondir', 'Json Dir')
		# allow user to click link to go to directory



	def CreateDirSelectWidget(self, parent, varname, label):
		"""this creates a label, a text field to hold the directory name, and a button to open a dir selector dialog.
		This method DOES NOT bind the events"""
		lbl = Label( parent, text=label, padx=5, bg=CFG_COLOR)
		lbl.pack( side=LEFT)
		widget = Entry(parent, width=MIN_DIR_BOX_WIDTH,  # path entry
			textvariable = self.ui[varname])
		widget.pack(side=LEFT, fill=X, expand=20)
		Button( parent, text = "...", command=lambda:self.UserSelectDirectory(widget, varname)).pack(side=LEFT)
		# allow user to click link to go to directory
		self.MakeLabelClickable(lbl, lambda w = widget:self.OpenInSystem(widget.get()), label = label)
		return widget
		
	def AddYearSelector(self, parent):
		"""Create dropdown selector for years"""
		Label(parent, text='Year').pack(side=TOP)
		yr_option = OptionMenu(parent, self.ui['year'], *BasisRetrApp.YEARS)
		yr_option.pack(side=TOP)
		
	def AddMonthSelector(self, parent):
		"""Create Listbox for user to select a month"""
		# calendar.mo_abbr has an extra entry at index zero, need to ignore that, hence the -1
		Label(parent, text='Month').pack(side=TOP)
		self.mo = Listbox(parent, listvariable=self.ui['month'], height=len(calendar.month_abbr)-1, width=5, font = ("Arial",12),exportselection=0)
		self.mo.pack(side=TOP)
		self.mo.bind("<<ListboxSelect>>",self.OnUIChange)
		# build listbox using month names
		for i,mname in enumerate(calendar.month_abbr):
			if i==0: continue # ignore month zero--doesn't refer to anything
			self.mo.insert(i-1, " "+mname)

	def AddSyncButton(self, parent, side = TOP):
		catch_up = Button( parent, text = " Sync ", fg='#009', font=self.SYNC_BUTTON_FONT, padx=3)
		catch_up.pack(side=side, padx=6)
		catch_up.bind("<ButtonRelease-1>", self.OnSync)		
		
	def AddSummaryButtons(self, parent, side=TOP):
		"""Add buttons to collect month summaries"""
		# activities summary
		Label(parent, text=' Month Summaries:').pack(side=side)
		self.mo_act = Label(parent, text='act_siz', padx=5)
		self.mo_act.pack(side=side)
		dl_actys = Button( parent, text = "D/L activities")
		dl_actys.pack(side=side)
		dl_actys.bind("<ButtonRelease-1>", self.OnGetActivitiesForMonth)
		
		# sleep events summary
		self.mo_sleep = Label(parent, text='slp_siz', padx=5)
		self.mo_sleep.pack(side=side)
		dl_sleep = Button( parent, text = "D/L sleep")
		dl_sleep.pack(side=side)
		dl_sleep.bind("<ButtonRelease-1>", self.OnGetSleepForMonth)
		

	def SetHandlers(self):
		"""Set event handlers. Mostly for ensuring config object is consistent with UI."""
		self.ui['loginid'].trace("w", self.OnUIChangeNoUpdate)
		self.ui['passwd'].trace("w", self.OnUIChangeNoUpdate)
		# don't want to update each character change, only onfocusout.
		# actually, FocusOut also triggers a lot us useless events (e.g., when the value wasn't actually changed)
		self.dir_text.bind("<FocusOut>",lambda x:self.OnSaveDirChange('savedir', self.bretr.app_state.savedir))
		self.dir_text.bind("<Return>",lambda x:self.OnSaveDirChange('savedir', self.bretr.app_state.savedir))
		
		#### expect no longer needed.  Remove when this is confirmed.
		#self.jsondir_text.bind("<FocusOut>",lambda x:self.OnSaveDirChange('jsondir', self.bretr.app_state.savedir))
		#self.jsondir_text.bind("<Return>",lambda x:self.OnSaveDirChange('jsondir', self.bretr.app_state.savedir))
		#self.ui['json_csv'].trace("w", self.OnUIChange)
		self.ui['year'].trace("w", self.OnUIChange)

	def PopulateData(self, day=None):
		"""Populate the center of the screen (i.e., each day in the selected month) with file data.  Scan user-selected directory, show info on files for selected month, along with download buttons.  Can update UI for a single day only (by setting 'day' param) or for the entire month (day = None).""" 
		# Data for month is shown in 2 columns.
		# Left side (columns 0-4) is first half of month
		# Right side (columns 5-9) is for 2nd half
		# note dirs that don't exist
		if not os.path.isdir(self.GetUI('savedir')):
			self.Status("directory {} doesn't exist".format(self.GetUI('savedir')))
			return
		
		# yr and mo are  both strings from the UI-- coerce to int
		yr, mo = int(self.GetUI('year')), int(self.GetUI('month')[0])
		days_in_month = calendar.monthrange(yr, mo+1)[1]
		#### expect no longer needed.  Remove when this is confirmed.
		#json_csv = SHOW_JSON_OR_CSV#self.GetUI('json_csv')
		#act_metr = ACTIVITY_TYPE_INTO_METRICS #self.GetUI('act_metr')
		
		ui_colnames = ACTIVITY_TYPE_INTO_METRICS and qw('Date Metrics Download') or qw('Date Metrics Download Sleep Download')
		launch_dirname = os.path.abspath(self.bretr.app_state.savedir)
		#### several commented lines below: expect no longer needed.  Remove when this is confirmed.
		#launch_dirname = json_csv == 'json' and self.bretr.GetJsonStorageDir() or os.path.abspath(self.bretr.app_state.savedir)
		full_dirname = os.path.abspath(launch_dirname)
		# First, retrieve file info (i.e., size) for this month. size = 0 means no file.  Otherwise, we'll display size in ui.
		metrics_sizes, activities_sizes, sleep_sizes = self.GetFileData(yr, mo,days_in_month)
		#metrics_sizes, activities_sizes, sleep_sizes = self.GetFileData(yr, mo,days_in_month, json_csv)
		if len(metrics_sizes)==0: # ignore if no results
			metrics_sizes = [None]
		# make date range: either entire month or for a single day if one was passed in.
		if day: 
			date_range = range(day-1, day)
		else: # redraw entire month
			date_range = range(days_in_month)
			# the following clears the frame so that when we redraw,
			# bits from the prior frame don't show through
			# THOUGH the clear/redraw process is jarring
			self.data_frame.forget()
			self.data_frame = Frame(self.master)
			self.data_frame.pack(side = LEFT, fill=BOTH)
		
		# header row-- create column headings
		fr = self.data_frame # container where the data goes
		for coff in [0,len(ui_colnames)]: # left hand side, then right hand side
			for (c, lbl) in enumerate(ui_colnames):
				Label(fr, text=lbl).grid(row=0, column=coff+c)
				
		# Column and row offsets for dealing with columns
		coff = 0 
		roff = 1 # start at 1 to account for column heading
		# TkFont.Font requires root frame ("master" here) to exist, so can't make it a class variable.
		for r in date_range:
			## What need here to separate into distinct method with yr, mo, day as params?
			#fr= self.data_frame
			#coff, roff = 0,1 if r < int(days_in_month/2) else len(ui.col_names), -int(days_in_month/2)+1
			# days_in_month = calendar.monthrange(yr, mo+1)[1]

			if r >= int(days_in_month/2): 
				# shift offsets for right hand side columns
				coff = len(ui_colnames)
				roff = -int(days_in_month/2)+1 # +1= account for header row
				# if displaying a month in the future (i.e., no text in cells), prevent the rows from scrunching up vertically.
				fr.grid_rowconfigure(r+roff, minsize = 25)
						
			# column zero: date
			d = date(yr, mo+1, r+1)
			dy = calendar.day_abbr[d.weekday()]
			# highlight weekend days
			bgcolor = d.weekday() in [5,6] and 'yellow' or None
			# show dates in the future with gray text
			today = date.today()
			# show future dates as gray
			fgcolor =  d > today and "dark gray" or None
			
			#dt= (BasisRetr.DATE_FMT.format(yr,mo+1,r+1)) # also used for filenames in click handlers below
			dt = self.bretr.YrMoDyToString(yr, mo+1, r+1)
			Label(fr, text=dt+" "+dy, anchor=W,fg=fgcolor, bg = bgcolor, padx = 5).grid(row=r+roff, column=coff+0, sticky=W+E+N+S )
			

			# column 1: metrics file size or "--" if no file. Make file size clickable, and style like browser hyperlink
			lbl_text = metrics_sizes[r] or "  --  "
			lbl = Label(fr, text=str(lbl_text)+'uu')
			lbl.grid(row=r+roff, column=coff+1)
			fname = self.bretr.CFG.day_fname_template.format(date=d, typ='metrics', fmt='csv')
			#fname = self.bretr.CFG.day_fname_template.format(date=d, typ='metrics', fmt=json_csv)
	
			fpath = os.path.join(full_dirname, fname)
			day_is_complete = self.bretr.DayMetricsJsonIsComplete(dt)
			self.MakeLabelClickable(lbl, fpath, is_complete = day_is_complete)
			
			# dates in the future are empty rows
			if d > today:
				continue

			# column 2: metrics download button
			btext = 'metrics %02d' % (r+1)
			b = Button(fr, text=btext,borderwidth=1)
			b.grid(row=r+roff, column = coff+2, ipady=0)
			b.bind("<ButtonRelease-1>", self.OnGetDayData)
		
		# Update all-month statistics (activities and sleep)
		fname = self.bretr.CFG.mo_fname_template.format(yr=yr, mo=mo+1, typ='activities')
		self.MakeLabelClickable(self.mo_act, os.path.join(full_dirname, fname))
		fname = self.bretr.CFG.mo_fname_template.format(yr=yr, mo=mo+1, typ='sleep')
		self.MakeLabelClickable(self.mo_sleep, os.path.join(full_dirname, fname))
		
	def MakeLabelClickable(self, widget, action, label = None, is_complete = True):
		"""Turn a text label into a clickable link.  Label default is the size of the passed-in file"""
		# TkFont.Font requires root frame ("master" here) to exist, so can't make it a class variable.
		if hasattr(action, "__call__"): # is action a function?
			f = action
		elif (type(action) == str or type(action) == unicode) and os.path.isfile(action):
			f = lambda e:self.OpenFileInSystem(action)
			if label is None: # default is file size
				label = os.path.getsize(action)
		else:
			f = None
		
		# first case is create link, second is regular text
		#widget['text']=f and label or "--"
		widget['text']= label if f else "--"
		widget['fg'] = 'blue' if f and is_complete else 'orange' if f else 'black'			
		widget['font'] = f and self.LINK_FONT or self.REGULAR_FONT 
		f and widget.bind("<Button-1>",f) or widget.unbind("<Button-1>")

	def OpenFileInSystem(self, fname):
		"""Open the passed in filename in whatever application is registered to handle it."""
		
		"""expect no longer needed.  Remove when this is confirmed.
		if self.GetUI('json_csv') == 'json':
			fpath = os.path.join(self.bretr.GetJsonStorageDir(), fname)
		else:
			fpath = os.path.join(os.path.abspath(self.bretr.app_state.savedir), fname)
		"""
		fpath = os.path.join(os.path.abspath(self.bretr.app_state.savedir), fname)
		self.OpenInSystem(fpath)

	def OpenInSystem(self, fpath):
		if not os.path.exists(fpath):
			# try adding basedir
			fpath = os.path.join(self.bretr.app_state.savedir, fpath)
		if not os.path.exists(fpath):
			self.Status("clicked '{}', but didn't open.".format(fpath))
		else:
			self.Status("Opening '{}'.".format(fpath))
			if ismac:
				cmd = fpath # seems we don't need to escape path: orig= escape_path_spaces(fpath)
				try:
					p = subprocess.Popen(['open',cmd])
				except Exception as e:
					print("Tried to open file but didn't: "+ `type(e)`+"=>"+`e`)
			else: # assume windows for now
				# could also do a generic "open" for file.  Directories don't work here, though.
				if os.path.isdir(fpath): # separate handling of directories
					cmd = 'explorer.exe "'+escape_path_spaces(fpath)+'"'
				else:
					cmd = 'cmd /c "start '+escape_path_spaces(os.path.realpath(fpath))+'"'
				try:
					p = subprocess.Popen(cmd, shell = True)
				except Exception as e:
					print("Tried to open file but didn't: "+ `type(e)`+"=>"+`e`)

	METRICS_RE= re.compile("metrics")
	ACTIVITIES_RE = re.compile("activities")
	SLEEP_RE = re.compile('sleep')
	def GetFileData(self, yr, mo, days_in_month):
#	def GetFileData(self, yr, mo, days_in_month, json_csv):
		"""Walk through directory (including subdirectories) and gather file sizes"""
		top_folder = self.GetUI('savedir')
		"""expect no longer needed.  Remove when this is confirmed.
		if json_csv == "json":
			top_folder = self.bretr.GetJsonStorageDir()		
		"""
		if not os.path.isdir(top_folder): # don't do anything if folder not defined.
			return [],[],[]
		# pre-compile regex's since we use these. These determine, from the filename, what kind of data is in the file 
		YrMo_re= re.compile('%04d-%02d-(\d\d)' % (yr, mo+1))
		type_re = re.compile('\.csv$')
		#### expect no longer needed.  Remove when this is confirmed.
		#type_re = re.compile('\.'+json_csv+'$')
		metrics= [None]*days_in_month
		activities = [None]*days_in_month
		sleep = [None]*days_in_month
		files = [ f for f in os.listdir(top_folder) if os.path.isfile(os.path.join(top_folder,f)) ]
		for name in files: # look for y-m match first
			d = type_re.search(name)
			m = YrMo_re.search(name)
			if not m or not d: continue 	# file is from another month or not the right type
				
			day = int(m.group(1))
			path = os.path.realpath(os.path.join(top_folder, name))
			size = os.path.getsize(path)

			try:
				if BasisRetrApp.METRICS_RE.search(name):
					metrics[day-1] = size
				if BasisRetrApp.ACTIVITIES_RE.search(name):
					activities[day-1] = size
				if BasisRetrApp.SLEEP_RE.search(name):
					sleep[day-1] = size
			except Exception, v:
				self.Status("Error gathering metrics for day"+`day`+":",`v`)
		return metrics, activities, sleep

	##		 Done populating UI
	##
	############################
	##
	##			Data Retrieval from Basis Website
	##
	def CheckRequiredData(self):
		"""Make sure have sufficient data from the UI before dealing with Basis servers"""
		id, pwd, d = self.GetUI('loginid'), self.GetUI('passwd'), self.GetUI('savedir')
		if id and pwd and d and os.path.isdir(d):
			return True
		else:
			if not os.path.isdir(d):
				self.Status("Save-to directory {} not found".format(d))
			else:
				self.Status("Retrieving data requires login id, password, and download directory; please fill in.")
			return
	
	def OnSync(self, evt):
		"""Catch up to current day. Downloads yesterday and back until it detects the first downloaded day."""
		override_cache = self.GetUI('override')
		#### expect no longer needed.  Remove when this is confirmed.
		#do_csv = self.GetUI('json_csv') == 'csv'
		#act_metr = True #self.GetUI('act_metr') # flag to add activities to metrics
		# set show current month.
		today = datetime.date.today()
		self.SyncCallback(today.year, today.month, today.day)
		# now, do the sync.
		self.bretr.Sync(True, override_cache, ACTIVITY_TYPE_INTO_METRICS, self.SyncCallback)
		#self.bretr.Sync(self.GetUI('json_csv') == 'csv', override_cache, ACTIVITY_TYPE_INTO_METRICS, self.SyncCallback)

	def SyncCallback(self, yr, mo, day):
		# first, make sure UI reflects current month and year we're downloading.
		ui_yr, ui_mo = int(self.GetUI('year')), int(self.GetUI('month')[0]+1)
		#print 'yr',yr, ui_yr, 'mo',mo, ui_mo
		if yr != ui_yr or mo != ui_mo: # change  to download data
			self.mo.selection_clear(ui_mo-1, END)
			self.mo.selection_set(mo-1)
			self.ui['year'].set(str(yr))
			self.SetUiFromConfig() # update UI
		self.PopulateData(day)
		self.FreezePrevention()

	def OnGetDayData(self, evt):
		"""Get either metrics or sleep json data from Basis website, convert it to csv if that's what the user wants.  Button name is how we get the date and type of data to download."""
		if not self.CheckRequiredData():
			return
		btn = evt.widget.config('text')[-1] # get the text shown on the button
		typ, day = btn[0], int(btn[1])
		# Get button text as btn.config('text')[-1].  This returns a tuple split by spaces.  date num is last item in tuple.
		mo, yr = int(self.GetUI('month')[0]+1), int(self.GetUI('year'))
		
		#do_csv = self.GetUI('json_csv') == 'csv'
		override_cache = self.GetUI('override')
		#act_metr = True #self.GetUI('act_metr') # flag to add activities to metrics
		
		self.bretr.GetDayData(yr, mo, day, typ, True, override_cache, ACTIVITY_TYPE_INTO_METRICS)
		#self.bretr.GetDayData(yr, mo, day, typ, do_csv, override_cache, ACTIVITY_TYPE_INTO_METRICS)
			# Update data in list
		self.PopulateData(day)

		
	def OnGetActivitiesForMonth(self, evt):
		"""Get a month's worth of activities"""
		if not self.CheckRequiredData():
			return
		yr, mo = int(self.GetUI('year')), int(self.GetUI('month')[0]+1)
		self.bretr.GetActivityCsvForMonth(yr, mo)
		self.PopulateData()

	def OnGetSleepForMonth(self, evt):
		"""Get a month's worth of sleep data"""
		if not self.CheckRequiredData():
			return
		yr, mo = int(self.GetUI('year')), int(self.GetUI('month')[0]+1)
		self.bretr.GetSleepCsvForMonth(yr, mo)
		self.PopulateData()
		
	def FreezePrevention(self):
		"""enable UI to retain currency by allowing control to pass back to the window manager."""
		self.update()
		time.sleep(0.5)
		#yield 0.5

	###########################
	##
	##		UI Helpers and Event Handlers
	##
	def GetUI(self, label):
		"""Get a widget's value based on the key name in self.ui"""
		if label == "month":
			w = self.mo
			cs = w.curselection()
			if len(cs)>0: # make sure a month was actually selected
				index = int(cs[0])
			else:
				index = 0 # default to first month of year
				self.mo.selection_set(index)

			value = w.get(index)
			return index, value
		else:
			return self.ui[label].get()
	
	def SetUI(self, label, value):
		if label == 'month':
			self.mo.selection_set(value)
		else:
			self.ui[label].set(value)
			
	def OnUIChange(self, *args):#name, index, op):
		"""Respond to UI context changes (year, month, json/csv) by redrawing table for month.  Different event handlers have different method signatures, but we ignore them (via *args) because we don't care."""
		self.PopulateData()
		
	def OnUIChangeNoUpdate(self, *args):
		"""Respond to UI change that has no effect on UI-- just update config."""
		self.GetConfigFromUI()
	
	def OnSaveDirChange(self, varname, current_value):
		# only update UI if user actually changed the value
		if self.GetUI(varname) != current_value:
			self.GetConfigFromUI()
			self.PopulateData()
			savedir = self.GetUI('savedir')
			msg = 'Storing files in {}' if os.path.isdir(savedir) else "Can't find dir {}."

			self.Status(msg.format(savedir))

	def Status(self, txt):
		self.status_bar.set(txt)
		if DEBUG:
			print ">>STATUS:",txt
		
	def UserSelectDirectory(self, widget, varname):
		"""This is the handler for the "..." save-to directory select button. Show a folder browser and set the directory."""
		currentdir = self.ui[varname].get()
		dirname = tkFileDialog.askdirectory(parent=self,initialdir=currentdir,title='Please select a directory')
		widget.delete(0,END)
		widget.insert(0,dirname)
		self.focus_set()
		if dirname: # don't change anything if user hit escape (i.e., dirname =="")
			self.ui[varname].set(os.path.realpath(dirname))
			self.GetConfigFromUI()
			self.PopulateData()
	
	###########################
	##
	##				Save and load config-related
	##
	def SetUiFromConfig(self):
		"""Set the value of each UI element from config"""
		cfg = self.bretr.app_state
		for k in self.ui.keys():
			if not hasattr(cfg,k): continue # not in cfg: continue
			v = getattr(cfg,k)
			if k == 'month':
				self.mo.selection_set(v[0])
			elif k in self.ui.keys():
				self.ui[k].set(v)

	def GetConfigFromUI(self):
		"""For each UI item, set config from the UI's value"""
		cfg = self.bretr.app_state
		for k, v in self.ui.items():
			if k not in cfg.__dict__:
				continue
			if k == 'month': # Tk handles listboxes differently than other UI element types
				try:
					setattr(cfg,k,self.mo.curselection()[0])
				except:
					pass
			else:
				setattr(cfg,k,v.get())

##				End of class BasisRetrApp
##
#####################

import pprint
def ppp(object):
	"""debugging support: pretty print any object"""
	pprint.PrettyPrinter().pprint(object)

def escape_path_spaces(path):
	"""turn each space in pathnames into " ".  Used when launching file in windows."""
	if ismac:
		return re.sub(" ","\\ ",path,99)
	else:
		return re.sub(" ","\" \"",path,99)

class ToggleFrame(Frame):
	def __init__(self, parent, **options):
			Frame.__init__(self, parent, **options)
			self.titleFrame=Frame(self)
			self.titleFrame.pack()
			self.subFrame=Frame(self)
			self.subFrame.pack(fill=X, expand=1)
			self.subFrameInfo = self.subFrame.pack_info()

	def toggle(self, event=None):
		if not bool(self.subFrame.winfo_manager()):
			self.subFrame.pack(self.subFrameInfo)
		else:
			self.subFrameInfo = self.subFrame.pack_info()
			self.subFrame.forget()

class StatusBar(Frame):
	def __init__(self, master):
		Frame.__init__(self, master, bg='yellow')
		self.label = Label(master, text="", bd=1,relief=SUNKEN, anchor=W)
		self.label.pack(side=BOTTOM, fill=BOTH)

	def set(self, format, *args):
		text = format % args
		self.label.config(text=text)
		self.label.update_idletasks()

	def clear(self):
		self.label.config(text="")
		self.label.update_idletasks()

import imp, os, sys

def main_is_frozen():
	return (hasattr(sys, "frozen") or # new py2exe
		hasattr(sys, "importers") # old py2exe
		or imp.is_frozen("__main__")) # tools/freeze

# If developing, no buffer for stdout
if not main_is_frozen():
	sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)


def get_main_dir():
	if main_is_frozen():
		return os.path.dirname(sys.executable)
	return os.path.dirname(sys.argv[0])

def main():
	import sys
	import traceback
	import tkinter_error

	# our own handler for uncaught exceptions
	def excepthook(type, value, tb):
			msg = '\n' + '=' * 80
			msg += '\nUncaught exception in BasisRetriever.exe:\n'
			msg += ''.join(traceback.format_exception(type, value, tb))
			msg += '=' * 80 + '\n'
			log(msg)
			label='Please copy the text and email to '+EMAIL_NAME+'@'+EMAIL_DOMAIN+'.\n'
			label += 'Dev will not use your email for anything else.'
			tkinter_error.tkinter_error(msg, title='Crap, a problem!', note=label, master=Tk())
			sys.exit(1)

	# plug our handler into the python system
	sys.excepthook = excepthook

	fr = BasisRetrApp(master)
	master.protocol("WM_DELETE_WINDOW", fr.OnClose)
	fr.mainloop()

master = Tk() # boy, it was mysterious that we had to set this var-

if __name__ == "__main__":
	main()

""" Version Log
v0: some initial UI. About to make year a dropdown select box.
v1: UI framework seems to be working correctly. About to add day-by-day table
v2: correctly downloading both metrics and activities as json data.  About to download csv and get scrollable grid (can't get to end of month as it falls off bottom of screen)
v3: CSV works.  Instead of scrollable for now, made days in 2 sets of columns-- wider, but don't have to deal with ScrollableFrame, which isn't working yet.  Also, now clearing frame when redrawing entire month.
	Next steps: save password scrambled, add column heads
v4: Cleanup, now saving password scrambled, column heads added, using status bar
v5: big cleanup, changing save-to folder now updates the ui
v6: Fixed name collision Bug: now referring to BasisRetr correctly.
v7: About to integrate with updated basis_retr.py (v6)
v8: (aligned with basis_retr v7.py): refactored metrics, activities, and sleep downloading correctly, csv + json.  Also got month of activities downloading correctly.  Launching csv files by clicking on file size number.
v9 (aligned with basis_retr v8): Fixed event handlers for option (drop-down) menus. Date grid now only allows selecting metrics and sleep to download-- changed activity and sleep summary data so that now it only downloads for an entire month (no more day-specific buttons).  Links to files now styled to look like browser hyperlinks. Weekend days now highlighted in yellow.
v10: cleanup and moved month summary download links/buttons to the 2nd config rows
v11 (aligned with basis_retr v9): more cleanup, some data validation before hitting basis's servers
v12 (aligned with basis_retr.py v9, for release 0.2) os-x compatibility.  Got working for opening files under mac, fixed config persistance bug.
v13 (aligned with basis_retr.py v10): Updated called methods names to be consistent with renamed basis_retr methods.  This was part of refactoring to process data in the python object realm.
v14 (aligned with basis_retr.py v11): clean up and got monthly summaries working with refactored processing methods.
v15 (aligned withbasis_retr.py v12): integrating activities into metrics csv file.  Next step is to integrate sleep event data.
v16 (aligned with basis_retr.py v13): Sleep data integrated. Still need to confirm data is correct.
 bm
v17 (aligned with basis_retr.py v14): fixed bug where fail metrics collection if no sleep events for that day.  Also added "cache override" checkbox to allow forcing redownload of json file.
v18 (aligned with basis_retr.py v15): Got json display and json dir config working correctly.  Next step is to move the guts of OnGetDayData() into basis_retr.py in prep for command line implementation.  After that, move column names to config file. THen move Config class to separate file.
v19 (aligned with basis_retr.py v16): Moved main method for downloading a single day's data into basis_retr.py. Next, move column names to config file. Then move Config class to separate file.
v20 (also basis_retr.py v17): Column names in config file. Config class is now separate file. Next step is cleanup.
v21 (also basis_retr.py v18): Minor cleanup while got command line version running.
v22 (also basis_retr.py v19): command line data retrieval tested and all versions seem to be working. Fixed bug where actually passing zero-based month to month summary retrievals
v23 (also basis_retr.py v20): External changes: added explicit jsondir to UI and config. UI now shows only metrics buttons/sizes if Add activities to metrics is checked (as sleep events is superfluous in that case). Fixed bug where no data at all saved for a given month results in no info in UI at all (should be dates and dashes for sizes). Changed "future date" text color to "dark gray"
Internal: packaged CreateDirSelectorWidget into its own method (along with UserSelectDirectory).  Renamed FormatSummaryCell to MakeLabelClickable and made method more generic (can accept arbitrary pathnames or lambdas and arbitrary labels.
v24 (also basis_retr.py v21): Cleanup.  Got datetime working as default fields. Tightened up month summary data processing. Reorganized config (upper) part of gui.
v25 (also basis_retr.py v25), 25 Sept 2014: Added feature to only download day if it's complete.  Also added 'Catch Up' capability- download all days that are missing.
v26 (also basis_retr.py v26), 3 Oct 2014: Removed "Only download complete days" switch (instead, will check and highlight incomplete days to user).  Improved robustness of checking for help file.  Uppercased "d/l" in button labels.  Updated per changes to filename templates in basis_retr.py.
v27, 4 Oct 2014: checking completeness for each file, color-coding orange if file data is incomplete (doesn't have all 24 hrs of data).
v28, (with basis_retr.py v28), 5 Oct 2014: minor layout mods, renamed CatchUp to Sync.
v29, 17 Apr 2015: before clean up and work on v0.5
v30, 18 Apr 2015: Reduced screen flicker during sync update in PopulateData() (by day instead of refreshing entire month).  Added stdout non-buffering only if in dev mode (via main_is_frozen()).  Organized CreateWidgets() a little.  Began work on toggle config details.
v31, 19 Apr 2015: Added tk errordialog for runtime errors+separate logfile. Made toggleable config rows. For status messages, only showing filename, not entire path (don't think it's needed).
v32 (with basis_retr.py v30), 23 Apr 2015: Abstracted dropdown config color, width of dir entry box, and "activity type into metrics" to constants. Removed "activity type into metrics" feature- now always creating csv files.  Added helpful text in status bar for initial startup. Added version number, visible in About box. Fixed bug where config area toggle state was not reflected in toggle button visual style (depressed).
v33 (with basis_retr.py v31), 25 April 2015: Removed json/csv switch, simplifying config UI.
"""