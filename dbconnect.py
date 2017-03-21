### Abstract the MySQLdb layer

import MySQLdb
import object_cache
import time
import datetime
import __main__
import sys


class db:

	_conn = None
	_db = None
	_port = 3306
	_cache = object_cache.objectCache()
	_use_cache = False
	_slow_queries = False
	_cache_ttl = 60
	_query_log = '/queries.log'
	_log_errors = False
	_ignore_errors = False
	_query_time = 0
	_slow_query_time = 10
	_last_query = ''
	_cache_used = False
	_content = None
	_is_connected = False
	_dbhost = ''
	_dbuser = ''
	_dbpass = ''
	
	def __init__(self, host = None, user =None, pwd = None, port = 3306 ):
		_is_connected = False
		self._dbhost = host
		self._port = port
		self._dbuser = user
		self._dbpass = pwd
		return
		
	def _connect(self, host = _dbhost, user = _dbuser, pwd = _dbpass ):
		self._conn = MySQLdb.connect(self._dbhost, self._dbuser, self._dbpass, charset='UTF8', port = self._port)
		self._db = self._conn.cursor(MySQLdb.cursors.DictCursor)
		self._is_connected = True
		return
		
	# Run a query to get a tuple (one dictionary per row); check for caching
	def getDict(self, sql, args=() ):
		if self._use_cache:
			if self._cache.read('query', sql + str(args)):
				self._cache_used = True
				self._last_query = sql
				self._content = self._cache.content()
			else:
				self._content = self._returnDict(sql, args)
				self._cache.write(self._content)
		else:
			self._content = self._returnDict(sql, args)
		return self._content
	
	# Return a single value, optimized for caching
	def getOne(self, sql, args=()):
		if self._use_cache:
			self._last_query = sql
			if self._cache.read('query',sql + str(args)):
				self._cache_used = True
				self._content = self._cache.content()
			else:
				d = self._returnDict(sql, args=args)
				self._content = d[0].itervalues().next()
				self._cache_used = False
				self._cache.write(self._content)
		else:
			d = self._returnDict(sql, args=args)
			if len(d) > 0:
				self._content = d[0].itervalues().next()
			else:
				self._content = None
			self._cache_used = False
		return self._content
	
	# Execute a query and return a tuple of dictionaries (for internal use)
	def _returnDict(self, sql, args=() ):
		if not self._is_connected:
			self._connect()
		start = time.time()
		try:
			self._db.execute(sql, args)
			self._content = self._db.fetchall()
		except Exception, e:
			if self._log_errors:
				self._logError(e, self._db._last_executed)
			self._content = False
			if self._ignore_errors:
				pass
			else:
				self._errorMsg(e, self._db._last_executed)
				sys.exit(1)
		self._last_query = self._db._last_executed
		if time.time() - start >= self._slow_query_time and self._slow_queries:
			self._query_time = time.time() - start
			self._logSlowQuery()
		self._cache_used = False
		return self._content
	
	def run(self, sql, args = (), commit = False):
		if not self._is_connected:
			self._connect()
		try:
			self._db.execute(sql, args)
			if commit:
				self._db.execute('COMMIT')
		except Exception, e:
			if self._log_errors:
				self._logError(e, self._db._last_executed)
			self._content = False
			if self._ignore_errors:
				pass
			else:
				self._errorMsg(e, self._db._last_executed)
				sys.exit(1)				
		return

	def runSkipErrors(self, sql, args = ()):
		if not self._is_connected:
			self._connect()
		try:
			self._db.execute(sql, args)
		except Exception, e:
			if self._log_errors:
				self._logError(e, self._db._last_executed)
			self._content = False
			if self._ignore_errors:
				pass
			else:
				self._errorMsg(e, self._db._last_executed)
				sys.exit(1)				
		return
	
		
	def runMany(self, sql, args = []):
		if not self._is_connected:
			self._connect()
		try:
			self._db.executemany(sql, args)
		except Exception, e:
			if self._log_errors:
				self._logError(e, self._db._last_executed)
			self._content = False
			if self._ignore_errors:
				pass
			else:
				self._errorMsg(e, self._db._last_executed)
				sys.exit(1)			
		return
	
	# Caching functions (enable, disable, change timing)
	def cache(self, ttl = _cache_ttl):
		self.setTTL(ttl)
		self._use_cache = True
		return
	
	def setTTL(self, ttl):
		self._cache_ttl = ttl
		self._cache.setTTL(ttl)
		return
	
	
	def noCache(self):
		self._use_cache = False
		return
	
	def cacheUsed(self):
		return self._cache_used
	
	def setCacheFolder(self, folder):
		self._cache.setCacheFolder(folder)
		return
	
	# Logging
	def logSlowQueries(self, on = True, t = _slow_query_time):
		self._slow_queries = on
		self._slow_query_time = t
		return

	def logErrors(self, on = True):
		self._log_errors = on
		return
	
	def ignoreErrors(self, on = True):
		self._ignore_errors = on
		return
	
	def _logError(self, e = '', sql = ''):
		msg = """ -------------------------------------------------------- 
						{!s} - QUERY ERROR in {!s}
						Error {!s} in query 
						{!s}
						 """.format(str(datetime.datetime.now()), __main__.__file__, e, sql).replace('\t','')
		self._log(msg)
		return
	
	def _errorMsg(self, e, sql):
		print "### ERROR {!s} in SQL: {!s}".format(e, sql)
		return
	
	def _logSlowQuery(self):
		msg = """ -------------------------------------------------------- 
						{!s} - Slow query in {!s}
						This query took {!s} seconds:
						{!s} 
						""".format(str(datetime.datetime.now()), __main__.__file__, '{0:.2f}'.format(self._query_time), self._last_query).replace('\t','')
		self._log(msg)
		return

	def _log(self, msg):
		with open (self._query_log, 'a') as logfile:
			logfile.write(msg)
		
	# Other

	def setLogFile(self, f):
		self._query_log = f
		return
	
	def testConnection(self):
		try:
			self._db.execute("SELECT 1")
		except:
			self._connect()
	
	
	def lastQuery(self):
		return self._last_query
	
	def lastInsertID(self):
		if not self._is_connected:
			self.connect()
		self._db.execute("SELECT last_insert_id() AS c")
		return self._db.fetchone()['c']
		
	def __repr__(self):
		return '<dbconnect %s @ %s, connected: %s>' % (self._dbuser, self._dbhost, self._is_connected)