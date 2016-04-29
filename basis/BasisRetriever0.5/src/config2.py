import re
# with help from http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/
# and http://www.decalage.info/en/python/configparser

"""
Goals: 
- simple 'option = value' format in the config file
- allow comments
- allow structured data.  json would be nice, general python structures even better.
- useful error checking

Solutions I could find have either nice format and commenting (YAML, .ini format) or structured data (json).  Python error handling for a json file doesn't seem very helpful. None have all of the above.
"""

class bunch(dict):
	"""simple container class, allowing both dict iteration and dot access"""
	def __init__(self, **kw):
		dict.__init__(self, kw)
		self.__dict__ = self
	__getattr__ = dict.__getitem__
	__contains__  = dict.__contains__ # implements the 'in' binary operator

class Config2(bunch):
	"""Simple config class.  read option = value from file.  option can be dotted notation.  Values can span across lines if succeeding lines are indented."""
	COMMENT_CHAR = '#'
	OPTION_CHAR =  '='
	def __init__(self, **kw):
		bunch.__init__(self, **kw)
	def Parse(self, filename):
		#self._options = {}
		self._state = ''
		error_text = ''
		value = ''
		f = open(filename)
		for li, line in enumerate(f):
			# First, remove comments:
			if self.HasComment(line):#re.search('#[^\'"]+$', line):
				# split on comment char, keep only the part before
				line, comment = line.split(Config2.COMMENT_CHAR, 1)
			sline = line.strip(' \t\n\r')
			# if indented text, accumulate before evaluating.
			if len(line)>0 and (line[0] == '  ' or line[0] == '\t'):
				value +='\n'+sline
				continue
			elif self._state == 'accumulate': # then done accumulating
				err_msg = self.SetValue(li, option, value)
				if err_msg:
					self._state = ''
					error_text += err_msg+"\n\n"
					continue
				#self.SetValue(li, option, value)

			# Second, find lines with an option=value:
			if len(sline) == 0:
				continue # don't care about blank lines
			elif re.search('(?:[A-Za-z0-9_]+\.?)+\s*=', sline):
				# split on option char:
				option, value = sline.split(Config2.OPTION_CHAR, 1)
				# strip spaces:
				option = option.strip()
				value = value.strip(' \t\n\r')

				self._state = 'accumulate'
			else:
				error_text += "Couldn't parsing config text, line= "+line+"\n"
		# need to do this for the last line of the file
		if self._state == 'accumulate': # then done accumulating
			self.SetValue(li, option, value)
		f.close()
		# send error text if there were problems.
		return error_text if error_text != '' else None

	def HasComment(self, line):
		# Remove quoted stuff from string before capturing comment char
		li2 = re.sub("'[^']+'",'',line)
		li3 = re.sub('"[^"]+"','',li2)
		return re.search(Config2.COMMENT_CHAR, li3)
				
		
	def SetValue(self, lineno, option, value):
		# eval accumulated expression
		try:
			set_value = eval(value)
		except Exception as v:
			print 'tete',type(v), v[0]
			error_result ='Ignoring parse error, line'+ `lineno`+'config file:\n'+value
			error_result +="\n  Error:"+`v`
			return error_result
		#curval = self.options
		self.SetObject(option, set_value)
				#print option,'set =',options 
		self._state = ''
		return None # lack of error means OK
		
	def SetObject(self, option, set_value):
		s = option.split('.')
		curdict = self#.options
		#curobject = self
		for i,u in enumerate(s):
			if not hasattr(curdict, u):#u not in curdict:
				curdict[u] = bunch()
				if i < len(s)-1:
					curdict = getattr(curdict, u)
			elif i < len(s)-1:
				curdict = getattr(curdict, u)
			if i == len(s)-1: # at end of parse: set the actual options value
				if type(set_value) == dict:
					curdict[u] = bunch(**set_value)
				else:
					curdict[u] = set_value
				#setattr(curdict,u,set_value)
				#curdict[u] = set_value

if __name__ == '__main__':
	options = Config2()	
	o = options.Parse('config_test1.cfg')
	print '\ndone:',o#.options
	#print '\nact-enums=',o.attrs['act_type']#['enums']
	#print '\nattrs',o.attrs.act_type#['agg_method']
	print '\n enumm',o.attrs.act_type.enums
	print o.attrs.steps
	print 'y-marg-limit',o.y_limit_margin
	print 'attr2 col', o.attr2.color

""" Versions

v1, 27 Aug 2014 (with BA v34.py): got working.  Works with dotted notation (for ease of typing) and with dict notation (for iterating).
"""