
"""

	BIG CASES CONTROL SCRIPT
	
	This script automates control of the @big_cases bot using Twitter mentions.
	
	Commands are accepted only from APPROVED users. Commands are:
	
		- follow [case name], No. [case number] in [court bluebook abbr.]. 
		  requires a literal case number and the precise court abbreviation
		  if successful, it will add the case to the roster and tweet an update
		  if not, it will reply with the reason
		  
		- Can you find the [party] case?
		  Find the most recent docket entry matching '%party%' and return the 
		  case number and title. Follow-ups are acceptable:
		  
		    - If it finds the case number, reply 'follow that one'
			  and the bot will add it to the list. If the reply also inclues
			  the phrase 'call it [alias].' you can specify an alias for the case.
			  For example, 'Follow that one. Call it Michael Cohen search warrant
			  case.'

		- Can you try that again?
		  Automatically try to re-up a document that didn't appear to download
		  correctly the last time. (Only works on the latest filing of this type
		  in this case, because tweets aren't associated with docket IDs.)
		  
		- When was the [court] feed last updated?
		  Get the elapsed time, in minutes, since a new filing was added for [court], or an error.
			  
		- If a non-approved users asks it to follow a case, reply with no.

"""
	
import dbconnect
import json
import random
import re
from bigcases_settings import settings
from pacer_rss_feeds import courts
from twython import Twython


# Approved users by screen name
APPROVED = ['bradheath', 'npenzenstadler', ]

# Lists of outgoing messages
NOTAPPROVED = ['Who dares disturb my slumber?', 
				'Nope. (But suggestions by DM are appreciated.)', 
				'Who are you?',
				'$50',
				'No problem. Just reply with your password.', 
				'New phone, who dis?',  ]
			
CANDO = ['Can do.',
			'Yeah, sure, fine.',
			'You bet.', 
			'Why not.',
			'Yeah, OK.', 
			'If you say so.', 
			'You\'re the boss.', ]

WELCOME = ['You\'re welcome.',
			'Sure, whatever.', 
			'Nothing could make a Twitter bot happier.', 
			'I live for this stuff!', ]
			
NOPE = ['Nope.',
	'Nah.', 
	'I\'m sorry, I\'m afraid I can\'t do that.',
	'Unfortunately, no.', ]

GOTITRIGHT = ['I\'m pretty sure I got it right the first time.',
			'Why?', 
			'Not really, no.', ]
	
# Regex control patterns	
FOLLOWPATTERN = re.compile('follow (.*?),? No. (.*?)\s{0,}(,|in|at) (.*?)[\?\,\!]{0,}$', re.IGNORECASE)
CLERKPATTERN = re.compile('go to the clerk', re.IGNORECASE)
FOLLOW = re.compile('^.{0,30} follow ', re.IGNORECASE)
FINDPATTERN = re.compile('find the (?:newest |latest :?)?(.*) case?', re.IGNORECASE)
FOLLOWTHAT = re.compile('follow that (one|case)', re.IGNORECASE)
CALLITPATTERN = re.compile('call it (.*?)\.$', re.IGNORECASE)
INPATTERN = re.compile('in (.*?)[\.\?\!]?$', re.IGNORECASE)
PRIORPATTERN = re.compile('mean (.*?), No. (.*?) in (.*?)\?', re.IGNORECASE)
THANKPATTERN = re.compile('(thank you|thanks)', re.IGNORECASE)
TRYAGAINPATTERN = re.compile('try that (?:one :?)?again', re.IGNORECASE)
NEWFILINGPATTERN = re.compile('filing in (.*?): (.*?)\n', re.IGNORECASE)
NOTINFEEDPATTERN = re.compile('not in the feed', re.IGNORECASE)
FEEDCHECKPATTERNS = [
	re.compile('latest feed from (.*)\?', re.IGNORECASE),
	re.compile('the (.*?) feed (?:last :?)?updated', re.IGNORECASE),
]

TITLECLEANPATTERN = re.compile('^(\d\:\d\d)-(cr|cv|mi|mc|ms|misc|sw)-([\d\-]{4,}) ', re.IGNORECASE)

db = dbconnect.db(host=settings.db_host, user=settings.db_user, pwd=settings.db_pass, port=settings.db_port)

case_file = open('bigcases.json')
case_data = json.load(case_file)
cases = case_data['cases']
cases_sct = case_data['supreme_court_cases']

# Check whether this case is already on the list
def check_case(case_number, court, sender):
	for c in cases:
		if c['case_number'] == case_number and c['court'] == court:
			return '@%s Good news! I already follow %s, No. %s (%s)' % (sender, c['name'], c['case_number'], c['court'])
	return 'new'

# Check on availability of records for this court. Return either a sorry message, a data note or nothing.
def check_court(court, sender):
	ct = any(a['id'] == court for a in courts)
	if not ct:
		return '@%s Sorry, I don\'t have a good data feed for %s yet so I can\'t do that.' % (sender, court)
	else:
		for c in courts:
			if c['id'] == court:
				if 'data_note' in c:
					return '(%s)' % c['data_note']
				else:
					return ''
				break
				
	
if __name__ == '__main__':

	reply = False

	tw = Twython(
		settings.twitter_app_key,
		settings.twitter_app_secret,
		settings.twitter_oauth_key,
		settings.twitter_oauth_secret
	)
	
	mentions = tw.get_mentions_timeline(count = 100)
	
	for mention in mentions:
		
		
		if db.getOne(""" SELECT COUNT(*) 
					FROM court.bigcases_mentions
					WHERE id = %s """, (mention['id'], )) == 0:

			print '[tw-m]->%s %s' % (mention['id'], mention['text'][:50].encode('ascii','ignore'))

					
			# This is a mention we have not seen before

			message = mention['text']
			sender = mention['user']['screen_name']
			sender_id = mention['user']['id_str']
			
			db.run(""" REPLACE INTO court.bigcases_mentions(id, txt, screen_name, user_id)
					VALUES(%s, %s, %s, %s) """,
					(mention['id'], mention['text'].encode('ascii','ignore'), sender, sender_id, ))
			
			# Check whether this is an approved requestor
			if sender.lower() in APPROVED:

				# Goof
				if CLERKPATTERN.search(message):
					msg = 'Sure. You just wait right there until I get back.'
					id = str(mention['id'])
					tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)
			
				# Get the latest feed update
				for p in FEEDCHECKPATTERNS:
					m = p.search(message)
					if m:
						court = m.group(1)
						court_msg = check_court(court, sender)						
						if 'Sorry' in court_msg:
							# If we don't follow that court, say so
							tw.update_status(status = '@' + sender + ' ' + court_msg, in_reply_to_status_id = str(mention['id']))
						else:
							r = db.getOne(""" SELECT MINUTE(TIMEDIFF(t.modified, NOW())) AS m
								FROM (
								SELECT modified
								FROM court.pacer_raw
								WHERE court = %s
								order by modified desc
								limit 1
								) AS t """, (court, ))
							LATEST = ['Looks like the latest item in the __court__ feed was from __minutes__ minutes ago.',
									'I found something from __court__ __minutes__ minutes ago.' ]
							l = random.choice(LATEST)
							l = l.replace('__court__',court)
							l = l.replace('__minutes__', str(r))
							msg = '@' + sender + ' ' + l
							tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
						break
			
				# Find if we have a case
				m = FINDPATTERN.search(message)
				if m:
					court_where = ''
					if INPATTERN.search(message):
						court_where = " AND court = '" + INPATTERN.search(message).group(1) + "' "
					
					c = db.getDict(""" SELECT *
									FROM court.pacer_raw
									WHERE title LIKE %s
										AND modified >= DATE_ADD(NOW(), INTERVAL -4  DAY)
										""" + court_where + """
									ORDER BY modified DESC
									LIMIT 1 """, ('%' + m.group(1) + '%', ))
									
					if len(c) == 0:
						
						msg = "@" + sender + " " + random.choice(NOPE)
						
					else:
						
						title = re.sub(TITLECLEANPATTERN, '', c[0]['title'])
					
						msg = "@" + sender + " Did you mean %s, No. %s in %s?" % (title, c[0]['case_number'], c[0]['court'] )
						
					tw.update_status(status = msg, in_reply_to_status_id = mention['id'])
			
				m = FOLLOWTHAT.search(message)
				if m and  mention['in_reply_to_status_id'] is not None:
				
					prior_id = mention['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id, tweet_mode='extended')
					
					m = PRIORPATTERN.search(prior['full_text'])
					if m:
						name = re.sub(TITLECLEANPATTERN, '', m.group(1))
						# If you've asked the case to have a particular name
						cpm = CALLITPATTERN.search(message)
						if cpm:
							name = cpm.group(1)
						
						case_number = m.group(2)
						court = m.group(3)
					
						new = check_case(case_number, court, sender)
						if new == 'new':

							# Add this to the list and update the file
							cases.append({'name':name, 'case_number': case_number, 'court':court })
							out = { 'supreme_court_cases': cases_sct, 'cases':cases }
							with open('/data/scripts/bigcases.json','w') as listfile:
								listfile.write(json.dumps(out, indent=4))

							filings = db.getDict(""" UPDATE court.pacer_raw
													SET bigcase = 1
													WHERE bigcase = 0
														AND case_number = %s
														AND court = %s
														AND modified >= DATE_ADD(NOW(), INTERVAL -12 HOUR)
													ORDER BY modified DESC
													LIMIT 10 """, (case_number, court, ))
							
							msg = '@' + sender + ' ' + CANDO[random.randint(0, len(CANDO) -1)]
							tw.update_status(status=msg, in_reply_to_status_id = str(mention['id']))
													
							# Tell us you have added it. Include any data notes for that court?
							msg = 'I\'m now following %s, No. %s in %s. %s' % (name, case_number, court, check_court(court, sender))
						
							tw.update_status(status = msg)
			
						else:
							# Oops, we already have this one
							msg = new
							tw.update_status(status = new, in_reply_to_status_id = str(mention['id']))

				elif THANKPATTERN.search(message) and mention['in_reply_to_status_id'] is not None:
				
					msg = '@' + sender + ' ' + random.choice(WELCOME)
					tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))

				elif TRYAGAINPATTERN.search(message) and mention['in_reply_to_status_id'] is not None:
					# This is asking me to try an upload again
										
					# First, get the previous status to figure out what to try again
					prior_id = mention['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id)
					
					
					# Then, see if it needs updating (does it have a DC link?)
					has_doc = False
					for u in prior['entities']['urls']:
						if 'documentcloud' in u['display_url']:
							has_doc = True
							break
							
					if has_doc:
						msg = '@' + sender + ' ' + random.choice(GOTITRIGHT)
						tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
					else:
						# Then, figure out what this was
						if NEWFILINGPATTERN.search(prior['text']):
							name = NEWFILINGPATTERN.search(prior['text']).group(1)
							desc = NEWFILINGPATTERN.search(prior['text']).group(2)
							
							# Figure out what case number goes with this
							cur_case = None
							for c in cases:
								if c['name'] == name:
									cur_case = c
									break
							
							# Now, look for records of this in the db
							pid = db.getOne(""" SELECT pid
											FROM court.pacer_raw
											WHERE court = %s
												AND case_number = %s
												AND description LIKE %s
											ORDER BY pid DESC
											LIMIT 1 """, 
											( c['court'], c['case_number'],
											'%' + desc + '%', ))
							if pid:
								# Mark it to try again
								db.run(""" UPDATE court.pacer_raw
											SET bigcase = 1
											WHERE pid = %s """,
											(pid, ))
								msg = '@' + sender + ' ' + random.choice(CANDO)
								tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
							else:
								# It didn't work
								msg = '@' + sender + ' ' + random.choice(NOPE)
								tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
								
						
						else:
							# You're trying to do something dumb
							msg = '@' + sender + ' ' + random.choice(NOPE)
							tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
							
						
			
				# Check whether this is a valid request
				m = FOLLOWPATTERN.search(message)
				if m:
					print 'Got your message'
					print 'New case: %s, No. %s in %s' % (m.group(1), m.group(2), m.group(4))
					case_number = m.group(2)
					court = m.group(4)
					name = m.group(1)

					# First, see if we already have it
					new = check_case(case_number, court, sender)
					if new == 'new':
						# Next, check to see if we have that court
						court_msg = check_court(court, sender)
						if 'Sorry' in court_msg:
							msg = court_msg
							reply = True
						else:
							# Next, check to see if it's in the db
							proc = False
							if NOTINFEEDPATTERN.search(message):
								# Continue without checking the db
								proc = True
							else:
								if db.getOne(""" SELECT COUNT(*) AS c
											FROM court.pacer_raw
											WHERE case_number = %s
												AND court = %s """, (case_number, court, )) == 0:
									reply = True
									msg = '@%s That case isn\'t in my database.' % sender
									proc = False
								else:
									proc = True
							if proc:
						
						
								# Add this to the list and update the file
								cases.append({'name':name, 'case_number': case_number, 'court':court })
								out = { 'supreme_court_cases': cases_sct, 'cases':cases }
								with open('/data/scripts/bigcases.json','w') as listfile:
									listfile.write(json.dumps(out, indent=4))
								
								# Go back and update some filings from today

								filings = db.getDict(""" UPDATE court.pacer_raw
													SET bigcase = 1
													WHERE bigcase = 0
														AND case_number = %s
														AND court = %s
														AND modified >= DATE_ADD(NOW(), INTERVAL -12 HOUR)
													ORDER BY modified DESC
													LIMIT 10 """, (case_number, court, ))

								# confirm
								msg = '@' + sender + ' ' + CANDO[random.randint(0, len(CANDO) -1)]
								tw.update_status(status=msg, in_reply_to_status_id = str(mention['id']))
													
								# Tell us you have added it. Include any data notes for that court?
								msg = 'I\'m now following %s, No. %s in %s. %s' % (name, case_number, court, check_court(court, sender))
						
					else:
						msg = new
						reply = True
						
					# Now post the message
					print 'RESULT: %s' % msg
					if reply:
						tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
					else:
						tw.update_status(status = msg)
		
			else: 
				# Not approved sender
				if mention['in_reply_to_status_id'] is None:
					if FOLLOW.search(message) or FINDPATTERN.search(message):
						print ' - Somebody has disturbed my slumbe'
						msg = NOTAPPROVED[random.randint(0, len(NOTAPPROVED) -1)]
						id = str(mention['id'])
						tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)

